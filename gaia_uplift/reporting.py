import json
import traceback
import prettytable as pt

import util
import git
import bzapi
import uplift
import configuration as c


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

def good_bug_comment(repo_dir, bug_id, bug):
    values = bug['flags_to_set']
    comment = ""
    for commit in bug['commits']:
        comment = "Uplifted %s to:\n" % commit
        for branch in bug['uplift_status'][commit]['success'].keys():
            branch_commit = bug['uplift_status'][commit]['success'][branch]
            if branch_commit == commit:
                comment += "%s already had this commit\n" % branch
            else:
                comment += "%s: %s\n" % (branch, branch_commit)
    try:
        bzapi.update_bug(bug_id, comment=comment, values=values)
    except Exception, e:
        print e
        traceback.print_exc()
        print "=" * 80
        print "Unable to comment on bug %s, please do this:" % bug_id
        print "https://bugzilla.mozilla.org/show_bug.cgi?id=%s" % bug_id
        print "Change these flags:"
        for flag in values.keys():
            print "  * %s -> %s" % (flag, values[flag])
        print "\nAnd make this this comment:"
        print comment


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


def bad_bug_comment(repo_dir, bug_id, bug):
    skip_this_comment = False
    bug_data = bzapi.fetch_complete_bug(bug_id)
    for c in [x['text'] for x in bug_data['comments']]:
        if c and 'git cherry-pick' in c:
            skip_this_comment = True
    comment = [
         "I was not able to uplift this bug to %s.  If this bug has dependencies " % util.e_join(bug['needed_on']) +
         "which are not marked in this bug, please comment on this bug.  " +
         "If this bug depends on patches that aren't approved for %s, " % util.e_join(bug['needed_on']) +
         "we need to re-evaluate the approval.  " +
         "Otherwise, if this is just a merge conflict, you might be able to resolve " +
         "it with:",
         ""]
    for commit in git.sort_commits(repo_dir, bug['commits'], 'master'):
        comment.append(merge_script(repo_dir, commit, bug['uplift_status'][commit]['failure']))
    comment = "\n".join(comment) #ugh
    if skip_this_comment:
        print "=" * 80
        print "Skipping this comment because there was already a merge resolution script"
        print ""
        print comment
        print ""
        return

    # If there is an assignee, try to needinfo them!
    flags = make_needinfo(bug_data)

    try:
        bzapi.update_bug(bug_id, comment=comment, values={}, flags=flags)
    except Exception, e:
        print e
        traceback.print_exc()
        print "=" * 80
        print "Unable to comment on bug %s, please do this:" % bug_id
        print "https://bugzilla.mozilla.org/show_bug.cgi?id=%s" % bug_id
        print "\nmake this this comment:"
        print comment

def ugly_bug_comment(repo_dir, bug_id, bug):
    values = bug['flags_to_set']
    comment = "This bug was partially uplifted.\n\n"
    bottom_of_comment = "\n"
    for commit in bug['commits']:
        if len(bug['uplift_status'][commit]['success'].keys()) > 0:
            comment += "Uplifted %s to:\n" % commit
        for branch in bug['uplift_status'][commit]['success'].keys():
            branch_commit = bug['uplift_status'][commit]['success'][branch]
            if branch_commit == commit:
                comment += "%s already had this commit\n" % branch
            else:
                comment += "%s: %s\n" % (branch, branch_commit)
        for branch in bug['uplift_status'][commit]['failure']:
            bottom_of_comment += "Commit %s didn't uplift to branch %s\n" % (commit, branch)
    comment += bottom_of_comment

    # If there is an assignee, try to needinfo them!
    flags = make_needinfo(bug_data)

    try:
        bzapi.update_bug(bug_id, comment=comment, values=values, flags=flags)
    except Exception, e:
        print e
        traceback.print_exc()
        print "=" * 80
        print "Unable to comment on bug %s, please do this:" % bug_id
        print "https://bugzilla.mozilla.org/show_bug.cgi?id=%s" & bug_id
        print "Change these flags:"
        for flag in values.keys():
            print "  * %s -> %s" % flag, values[flag]
        print "\nAnd make this this comment:"
        print comment
        print "-"*80
        print bug


def comment(repo_dir, report):
    good = [] # All commits on all branches
    bad = [] # No commits
    ugly = [] # Partial uplift
    good, bad, ugly = classify_gbu(report)

    def x(bug_id):
        del report[bug_id]
        util.write_json(uplift.uplift_report_file, report)

    for bug_id in good:
        print "Commenting on good bug %s" % bug_id
        good_bug_comment(repo_dir, bug_id, report[bug_id])
        x(bug_id)
    for bug_id in bad:
        print "Commenting on bad bug %s" % bug_id
        bad_bug_comment(repo_dir, bug_id, report[bug_id])
        x(bug_id)
    for bug_id in ugly:
        print "Commenting on ugly bug %s" % bug_id
        ugly_bug_comment(repo_dir, bug_id, report[bug_id])
        x(bug_id)

