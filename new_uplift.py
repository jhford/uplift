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


def make_merge_comment(repo_dir, commit, branches):
    s=["""\nCommit %s does not apply to %s.  This means that there are merge
conflicts which need to be resolved.  If there are dependencies that are not
approved for branch landing, or have yet to land on master, please let me know

If a manual merge is required, a good place to start might be:\n  cd gaia""" % (commit, util.e_join(branches, t="or"))]
    master_num = git.determine_cherry_pick_master_number
    if not master_num:
        master_num = ""
    s.append("  git checkout %s" % branches[0])
    s.append("  git cherry-pick -x %s %s" % (master_num, commit))
    s.append("  <RESOLVE MERGE CONFLICTS>")
    for branch in branches[1:]:
        s.append("  git checkout %s" % branch)
        s.append("  git cherry-pick -x $(git log -n1 %s)" % branches[0])
    return "\n".join(s)


def act_on_uplifted_bug(repo_dir, bug_id, bug):
    for commit in bug['commits']:
        print "Commit %s was uplifted to:" % commit
        for branch in bug['uplift_status'][commit]['success'].keys():
            print "%s@%s" % (branch, bug['uplift_status'][commit]['success'][branch])
    for commit in bug['commits']:
        failed_branches = bug['uplift_status'][commit]['failure']
        if len(failed_branches) > 0:
            print make_merge_comment(commit, failed_branches)



def act_on_uplift_report(repo_dir, report):
    for bug_id in report.keys():
        bug = report[bug_id]
        print "="*80
        if bug.has_key('uplift_status'):
            print "An uplift was attempted for bug %s" % bug_id
            act_on_uplifted_bug(repo_dir, bug_id, bug)
        else:
            print "Bug %s was skipped" % bug_id


def find_commits_for_bug(repo_dir, bug_id):
    """ Given a bug id, let's find the commits that we care about.  Right now, make the hoo-man dooo eeeet"""
    git.run_cmd(["open", "https://bugzilla.mozilla.org/show_bug.cgi?id=%d" % int(bug_id)], workdir='.')
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


with open(query_file, 'rb') as f:
    queries = [x.strip() for x in f.readlines()]


#uplift(gaia_path, bugs_needing_uplift, True)

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
    act_on_uplift_report(gaia_path, uplift_report)







