#!/usr/bin/env python
""" This is a new version of uplift.py"""
import os
import sys

import copy
import json

import prettytable as pt

import git
import bzapi
import branch_logic
import util

gaia_path = os.path.abspath(os.path.join(os.getcwd(), 'uplift-gaia'))
gaia_url = "github.com:mozilla-b2g/gaia.git"
query_file = os.path.abspath("uplift_queries.dat")


# Should be smarter about these cache files and either manage them in sets
# or use a single file which contains *all* the information only ever added to
requirements_cache_file = os.path.abspath("requirements.json")
uplift_cache_file = os.path.abspath("uplift.json")
uplift_report_file = os.path.abspath("uplift_report.json")

def read_cache_file(name, path):
    if os.path.exists(path) and util.ask_yn("Found %s cached data (%s).\nLoad this file?" % (name, path)):
        with open(path, 'rb') as f:
            return json.load(f)
    return None


def write_cache_file(data, path):
    with open(path, 'wb+') as f:
        json.dump(data, f, indent=2, sort_keys=True)


def find_bugs(queries):
    bug_data = []
    for q in queries:
        query = bzapi.parse_bugzilla_query(q)
        search_data = bzapi.search(query)
        for bug in search_data:
            if not bug in bug_data:
                bug_data.append(bug)
    return bug_data


def trim_words(s, max=90):
    if len(s) <= max:
        return s
    else:
        i = max - 3
        while s[i] != ' ':
            i -= 1
        return s[:i] + '...'


def display_uplift_requirements(requirements, max_summary=90):
    """Generate a PrettyTable that shows the bug id, branch status
    and first up to 100 chars of the summary"""
    headers = ['Bug'] + ['%s status' % x for x in branch_logic.branches] + ['Summary']
    t = pt.PrettyTable(headers)
    t.align['Bug'] = "l"
    t.align['Summary'] = "l"
    for bug_id in requirements.keys():
        bug = requirements[bug_id]
        row = [bug_id]
        needed_on = bug['needed_on']
        fixed_on = bug['already_fixed_on']
        for branch in branch_logic.branches:
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
    headers = ['Bug'] + ['%s commit' % x for x in ['master'] + branch_logic.branches] + ['Summary']
    t = pt.PrettyTable(headers)
    t.align['Bug'] = "l"
    t.align['Summary'] = "l"
    for bug_id in report.keys():
        bug = report[bug_id]
        row = [bug_id]
        master_commits = bug['commits']
        row.append("\n".join([x[:7] for x in master_commits]) if len(master_commits) > 0 else "skipped")
        for branch in branch_logic.branches:
            branch_commits = []
            for mcommit in master_commits:
                if bug.has_key('uplift_status'):
                    if branch in bug['uplift_status'][mcommit]['success'].keys():
                        branch_commits.append(bug['uplift_status'][mcommit]['success'][branch])
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
        s.append("  git cherry-pick -x $(git log -n1 %s)" % branches[0])
    return "\n".join(s)


def display_good_bug_comment(repo_dir, bug_id, bug):
    """Print everything that's needed for a good bug"""
    print "="*80
    print "COMMENT FOR BUG https://bugzilla.mozilla.org/show_bug.cgi?id=%s" % bug_id
    print
    print "Set these flags:"
    for flag in bug['flags_to_set'].keys():
        print "  * %s -> %s" % (flag, bug['flags_to_set'][flag])
    print
    print "Make this comment:"
    for commit in bug['commits']:
        print "Uplifted commit %s as:" % commit
        for branch in bug['uplift_status'][commit]['success'].keys():
            print "%s: %s" % (branch, bug['uplift_status'][commit]['success'][branch])
    print "-"*80
    print
    
def display_bad_bug_comment(repo_dir, bug_id, bug):
    """Print everything that's needed for a bad bug"""
    print "="*80
    print "COMMENT FOR BUG https://bugzilla.mozilla.org/show_bug.cgi?id=%s" % bug_id
    print
    print "I was not able to uplift this bug to %s.  If this bug has dependencies" % util.e_join(bug['needed_on']),
    print "which are not marked in this bug, please comment on this bug.  ",
    print "If this bug depends on patches that aren't approved for %s," % util.e_join(bug['needed_on']),
    print "we need to re-evaluate the approval.",
    print "Otherwise, if this is just a merge conflict, you might be able to resolve",
    print "it with:"
    print
    for commit in git.sort_commits(repo_dir, bug['commits'], 'master'):
        print merge_script(repo_dir, commit, bug['uplift_status'][commit]['failure'])
    print "-"*80
    print
    
def display_ugly_bug_comment(repo_dir, bug_id, bug):
    """Print everything that's needed for an ugly bug"""
    print "="*80
    print "BUG https://bugzilla.mozilla.org/show_bug.cgi?id=%s IS MESSED UP!" % bug_id
    print
    json.dump(bug, sys.stdout, indent=2, sort_keys=True)
    print "-"*80
    print
    
def classify_gbu(report):
    """I figure out which bugs are good, bad and ugly.  Good means that everything
    that was desired happened.  Bad means that nothing happened.  Ugly means that
    there was partial success"""
    good = []
    bad = []
    ugly = []
    for bug_id in [x for x in report.keys() if report[x].has_key('uplift_status')]:
        n_success = n_failure = 0
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
            raise Exception("What the hell is going on here!")
    return good, bad, ugly


def display_uplift_comments(repo_dir, report):
    skipped_bugs = [x for x in report.keys() if not report[x].has_key('uplift_status')]
    print "Skipped bugs: [%s]" % (", ".join(skipped_bugs))
    good = [] # All commits on all branches
    bad = [] # No commits
    ugly = [] # Partial uplift
    good, bad, ugly = classify_gbu(report)
    print "Good Bugs: %s" % ", ".join(good)
    print "Bad Bugs: %s" % ", ".join(bad)
    print "Ugly Bugs: %s" % ", ".join(ugly)
    for bug_id in good:
        display_good_bug_comment(repo_dir, bug_id, report[bug_id])
    for bug_id in bad:
        display_bad_bug_comment(repo_dir, bug_id, report[bug_id])
    for bug_id in ugly:
        display_ugly_bug_comment(repo_dir, bug_id, report[bug_id])

def open_bug(bug_id):
    """I know how to open a bug for inspection"""
    if sys.platform == "darwin":
        git.run_cmd(["open", "https://bugzilla.mozilla.org/show_bug.cgi?id=%d" % int(bug_id)], workdir='.')
    elif sys.platform == "linux2":
        git.run_cmd(["firefox", "https://bugzilla.mozilla.org/show_bug.cgi?id=%d" % int(bug_id)], workdir='.')


def find_commits_for_bug(repo_dir, bug_id):
    """ Given a bug id, let's find the commits that we care about.  Right now, make the hoo-man dooo eeeet"""
    open_bug(bug_id)
    # TODO:  This function should be smarter.  It should scan the bug comments and attachements and 
    #        see if it can find sha1 sums which point to the master branch commit information.  
    #        This function should also take a 'from_branch' parameter to figure out which branch
    #        the changes are coming from
    commits=[]
    prompt = "Type in a commit that is needed for %s or 'done' to end: " % bug_id
    user_input = raw_input(prompt).strip()
    while user_input != 'done':
        if git.valid_id(user_input):
            try:
                full_rev = git.get_rev(repo_dir, id=user_input)
                print "appending %s to the list of revisions to use" % full_rev
                commits.append(full_rev)
            except sp.CalledProcessError, e:
                print "This sha1 commit id (%s) is valid but not found in %s" % (user_input, repo_dir)
        else:
            print "This is not a sha1 commit id: %s" % user_input
        user_input = raw_input(prompt).strip()
    return commits


def find_commits(repo_dir, requirements):
    r = copy.deepcopy(requirements)
    any_bug_has_commits = False
    for bug_id in r:
        if len(r[bug_id].get('commits', [])) > 0:
            any_bug_has_commits = True
            break
    if util.ask_yn("Some bugs already have commits.  Reuse them?"):
        return r
    for bug_id in requirements.keys():
        if len(r[bug_id].get('commits', [])) > 0:
            print "Found commits ['%s'] for bug %s" % ("', '".join(r[bug_id]['commits']), bug_id)
            if not util.ask_yn("Would you like to reuse these commits?"):
                r[bug_id]['commits'] = find_commits_for_bug(repo_dir, bug_id)
        else:
            r[bug_id]['commits'] = find_commits_for_bug(repo_dir, bug_id)
    return r


def order_commits(repo_dir, requirements):
    commits = []
    for bug_id in requirements.keys():
        commits.extend(requirements[bug_id]['commits'])
    return git.sort_commits(repo_dir, commits, "master")


def uplift_bug(repo_dir, bug_id, commit, to_branches, from_branch="master"):
    """Uplift bug_id from branch to to_branches.  Return successful branches"""
    uplift_info = {'success': {},
                   'failure': []}
    for branch in to_branches:
        new_rev = git.cherry_pick(repo_dir, commit, branch, from_branch)
        if new_rev:
            uplift_info['success'][branch] = new_rev
        else:
            uplift_info['failure'].append(branch)
    return uplift_info


def uplift(repo_dir, requirements, start_fresh=True):
    """We want to take a repository and the uplift requirements and:
        1: clean up the gaia repository
        2: find all the commits for the bugs
        3: order the commits
        4: uplift the commits in the correct order

    We also want to add information to the requirments about:
        1: which branches the patches were uplifted to
        2: which branches failed
        3: which branches have open dependencies"""
    if start_fresh:
        git.delete_gaia(repo_dir)
    t=util.time_start()
    if os.path.exists(repo_dir):
        print "Updating Gaia"
        git.update_gaia(repo_dir, gaia_url)
        print "Updated Gaia in %0.2f seconds" % util.time_end(t)
    else:
        print "Creating Gaia"
        git.create_gaia(repo_dir, gaia_url) # This is sadly broken
        print "Created Gaia in %0.2f seconds" % util.time_end(t)

    with_commits = find_commits(repo_dir, requirements)
    write_cache_file(with_commits, requirements_cache_file)
    ordered_commits = order_commits(repo_dir, with_commits)

    uplift = dict([(x, {}) for x in ordered_commits])

    print "Commits in order:"
    for commit in ordered_commits:
        print "  * %s" % commit

    for commit in ordered_commits:
        needed_on = []
        for bug_id in with_commits.keys():
            if commit in with_commits[bug_id]['commits']:
                for i in with_commits[bug_id]['needed_on']:
                    if not i in needed_on:
                        needed_on.append(i)
        uplift[commit]['needed_on'] = needed_on
        uplift[commit]['uplift_status'] = uplift_bug(repo_dir, bug_id, commit, needed_on)

    uplift_report = copy.deepcopy(with_commits)

    for bug_id in uplift_report.keys():
        successful_branches = []
        failed_branches = []
        for commit in uplift_report[bug_id]['commits']:
            if commit in uplift.keys():
                if not uplift_report[bug_id].has_key('uplift_status'):
                    uplift_report[bug_id]['uplift_status'] = {}
                u = uplift_report[bug_id]['uplift_status']
                u[commit] = copy.deepcopy(uplift[commit]['uplift_status'])
                failed_branches.extend([x for x in u[commit]['failure'] if x not in failed_branches])
                successful_branches.extend([x for x in u[commit]['success'].keys() if x not in successful_branches])
        # Because we might have multiple commits, we want to make sure that the list of successful branches
        # includes only those with *no* failing uplifts
        for i in range(0, len(successful_branches)):
            if successful_branches[i] in failed_branches:
                del successful_branches[i]
        uplift_report[bug_id]['flags_to_set'] = branch_logic.flags_to_set(successful_branches)

    write_cache_file(uplift_report, uplift_report_file)
    return uplift_report


def build_uplift_requirements(repo_dir, queries):
    bug_info = read_cache_file("uplift information", requirements_cache_file)
    if not bug_info:
        bug_info = {}
        bugs = dict([(x, bzapi.fetch_bug(x)) for x in find_bugs(queries)])
        for bug_id in bugs.keys():
            b = bug_info[bug_id] = {}
            bug = bugs[bug_id]
            b['needed_on'] = branch_logic.needed_on_branches(bug)
            b['already_fixed_on'] = branch_logic.fixed_on_branches(bug)
            b['summary'] = bug['summary']
        write_cache_file(bug_info, requirements_cache_file)
    return bug_info


if __name__ == "__main__":
    with open(query_file, 'rb') as f:
        queries = [x.strip() for x in f.readlines()]

    if len(sys.argv) < 2:
        print "You must specify a command"
        exit(1)

    cmd = sys.argv[1]
    cmd_args = sys.argv[1:]

    if cmd == 'show':
        bugs = build_uplift_requirements(gaia_path, queries)
        print "\n\nRequirements for Bug uplift:"
        print display_uplift_requirements(bugs)
    elif cmd == 'uplift':
        requirements = build_uplift_requirements(gaia_path, queries)
        print "\n\nUplift requirements:"
        print display_uplift_requirements(requirements)
        uplift_report = uplift(gaia_path, requirements)
        print display_uplift_report(uplift_report)
        display_uplift_comments(gaia_path, uplift_report)







