import json
import traceback
import prettytable as pt
import textwrap

import util
import git
import bzapi
import uplift
import configuration as c

class FailedToComment(Exception): pass

def trim_words(s, max=90):
    if len(s) <= max + 3:
        return s[:max]
    else:
        i = max - 2
        while s[i] != ' ':
            i -= 1
            if i == 0:
                return s[:max]
        return s[:i] + '...'


def display_uplift_requirements(requirements, max_summary=90):
    """Generate a PrettyTable that shows the bug id, branch status
    and first up to 100 chars of the summary"""
    branches = c.read_value('repository.enabled_branches')
    headers = ['Bug'] + ['%s status' % x for x in branches] + ['Summary']
    t = pt.PrettyTable(headers, sortby="Bug")
    t.align['Bug'] = "l"
    t.align['Summary'] = "l"
    for bug_id in [x for x in requirements.keys() if not uplift.is_skipable(x)]:
        bug = requirements[bug_id]
        row = [bug_id]
        needed_on = bug['needed_on']
        fixed_on = bug['already_fixed_on']
        for branch in branches:
            if branch in fixed_on:
                row.append("fixed")
            elif branch in needed_on:
                row.append("needed")
            else:
                row.append("---")

        t.add_row(row + [trim_words(bug['summary'])])
    return t


def display_uplift_report(report, max_summary=90):
    """Generate a PrettyTable that shows the bug id, branch status
    and first up to 100 chars of the summary"""
    branches = c.read_value('repository.enabled_branches')
    headers = ['Bug'] + ['%s commit' % x for x in ['master'] + branches] + ['Summary']
    t = pt.PrettyTable(headers, sortby="Bug")
    t.align['Bug'] = "l"
    t.align['Summary'] = "l"
    for bug_id in [x for x in report.keys() if not uplift.is_skipable(x)]:
        bug = report[bug_id]
        row = [bug_id]
        master_commits = bug['commits']
        row.append("\n".join([x[:7] for x in master_commits]) if len(master_commits) > 0 else "skipped")
        for branch in branches:
            branch_commits = []
            for mcommit in master_commits:
                if bug.has_key('uplift_status'):
                    if branch in bug['uplift_status'][mcommit]['success'].keys():
                        branch_commit = bug['uplift_status'][mcommit]['success'][branch]
                        if branch_commit == mcommit:
                            branch_commits.append("+++")
                        else:
                            branch_commits.append(branch_commit)
                    elif branch in bug['uplift_status'][mcommit]['failure']:
                        branch_commits.append("failed")
                    else:
                        branch_commits.append("---")
            if len(branch_commits) == 0:
                row.append("---")
            else:
                row.append("\n".join([x[:7] for x in branch_commits]))


        t.add_row(row + [trim_words(bug['summary'])])
    return t


def merge_script(repo_dir, commit, branches):
    full_commit = git.get_rev(repo_dir, commit)
    s=["  git checkout %s" % branches[0]]
    master_num = git.determine_cherry_pick_master_number(repo_dir, commit, 'master')
    if not master_num:
        master_num = ""
    s.append("  git cherry-pick -x %s %s" % (master_num, full_commit))
    s.append("  <RESOLVE MERGE CONFLICTS>")
    s.append("  git commit")
    for branch in branches[1:]:
        s.append("  git checkout %s" % branch)
        s.append("  git cherry-pick -x $(git log -n1 %s --pretty=%%H)" % branches[0])
    return "\n".join(s)


def classify_gbu(report):
    """I figure out which bugs are good, bad and ugly.  Good means that everything
    that was desired happened.  Bad means that nothing happened.  Ugly means that
    there was partial success"""
    good = []
    bad = []
    ugly = []
    for bug_id in [x for x in report.keys() if report[x].has_key('uplift_status')]:
        n_success = 0
        n_failure = 0
        bug = report[bug_id]
        for commit in bug['uplift_status'].keys():
            n_success += len(bug['uplift_status'][commit]['success'].keys())
            n_failure += len(bug['uplift_status'][commit]['failure'])
        if n_success > 0 and n_failure > 0:
            ugly.append(bug_id)
        elif n_success > 0 and n_failure == 0:
            good.append(bug_id)
        elif n_failure > 0 and n_success == 0:
            bad.append(bug_id)
        else:
            raise Exception("What the hell is going on here! bug: " + bug_id +
                            " success: " + str(n_success) + " failure: "
                            + str(n_failure))
    return good, bad, ugly

def generate_good_bug_msg(bug):
    msg = ['Uplift successful']
    for commit in bug['commits']:
        msg.append("Uplifted %s to:" % commit)
        for branch in bug['uplift_status'][commit]['success'].keys():
            branch_commit = bug['uplift_status'][commit]['success'][branch]
            if branch_commit == commit:
                msg.append("  * %s already had this commit" % branch)
            else:
                msg.append("  * %s: %s" % (branch, branch_commit))
    return '\n'.join(msg)
    


def good_bug_comment(repo_dir, bug_id, bug):
    values = bug['flags_to_set']
    comment = generate_good_bug_msg(bug)
    try:
        bzapi.update_bug(bug_id, comment=comment, values=values)
    except Exception, e:
        raise FailedToComment({
            'exception': e,
            'traceback': traceback.format_exc()
        })


def make_needinfo(bug_data):
    flags = bug_data.get('flags', [])

    user = bzapi.load_credentials()['username']

    flags = [x for x in flags if x['name'] != user]

    if bug_data['assigned_to']['name'] != 'nobody@mozilla.org':
        requestee = bug_data['assigned_to']
    else:
        requestee = bug_data['creator']

    if requestee:
        flags.append({
            'name': 'needinfo',
            'requestee': requestee,
            'status': '?',
            'type_id': '800'
        })

    return flags

def generate_bad_bug_msg(repo_dir, bug):
    comment = [
        "I was not able to uplift this bug to %s.  " % util.e_join(bug['needed_on']),
        " If this bug has dependencies which are not marked in this bug ",
        "please comment on this bug.  If this bug depends on patches that ",
        "aren't approved for %s, " % util.e_join(bug['needed_on']),
        "we need to re-evaluate the approval.  ",
        "Otherwise, if this is just a merge conflict, ",
        "you might be able to resolve it with:"
    ]

    comment = textwrap.wrap(''.join(comment), 75)
    for commit in git.sort_commits(repo_dir, bug['commits'], 'master'):
        comment.append(merge_script(repo_dir, commit, bug['uplift_status'][commit]['failure']))


    return '\n'.join(comment)



def bad_bug_comment(repo_dir, bug_id, bug):
    # Short circuit for when we don't need to make a comment
    bug_data = bzapi.fetch_complete_bug(bug_id, cache_ok=True)
    for c in [x['text'] for x in bug_data['comments']]:
        if c and 'git cherry-pick' in c:
            return

    # If there is an assignee, try to needinfo them!
    flags = make_needinfo(bug_data)

    comment = generate_bad_bug_msg(repo_dir, bug)

    try:
        bzapi.update_bug(bug_id, comment=comment, values={}, flags=flags)
    except Exception, e:
        raise FailedToComment({
            'exception': e,
            'traceback': traceback.format_exc()
        })

def generate_ugly_bug_msg(bug):
    comment = ['This bug was partially uplifted.  This might not be valid']
    comment.append(generate_good_bug_msg(bug))
    comment.append('The following commits did not uplift:')
    for commit in bug['commits']:
        comment.append("  * %s failed on %s" % (commit, util.e_join(bug['uplift_status'][commit]['failure'])))
    
    return '\n'.join(comment)
    

def ugly_bug_comment(repo_dir, bug_id, bug):
    values = bug['flags_to_set']
    bug_data = bzapi.fetch_complete_bug(bug_id, cache_ok=True)
    flags = make_needinfo(bug_data)

    comment = generate_ugly_bug_msg(bug)

    try:
        bzapi.update_bug(bug_id, comment=comment, values=values, flags=flags)
    except Exception, e:
        raise FailedToComment({
            'exception': e,
            'traceback': traceback.format_exc()
        })


def comment(repo_dir, report):
    good = [] # All commits on all branches
    bad = [] # No commits
    ugly = [] # Partial uplift
    good, bad, ugly = classify_gbu(report)
    failed_bugs = []

    def x(bug_id):
        del report[bug_id]
        util.write_json(uplift.uplift_report_file, report)

    for i, j in (good, good_bug_comment), (bad, bad_bug_comment), (ugly, ugly_bug_comment):
        for bug_id in i:
            print "Commenting on bug %s" % bug_id
            try:
                j(repo_dir, bug_id, report[bug_id])
                x(bug_id)
            except FailedToComment:
                failed_bugs.append(bug_id)
                
    if len(failed_bugs) > 0:
        filename = os.path.abspath('failed_comments_%s.json' % util.time_str())
        print "The following bugs had commenting failures"
        print util.e_join(failed_bugs)
        print "Creating a file to use with the 'uplift comments' file to try just these."
        print "Fix the issue then run: uplift comments %s" % filename
        util.write_json(filename, report)

