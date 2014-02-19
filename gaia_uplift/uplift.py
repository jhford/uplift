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
import find_commits
import reporting
import configuration as c


# Should be smarter about these cache files and either manage them in sets
# or use a single file which contains *all* the information only ever added to
requirements_file = os.path.abspath("requirements.json")
uplift_report_file = os.path.abspath("uplift_report.json")
skip_bugs_file = os.path.abspath("skip_bugs.json")

def read_requirements(name, path):
    if os.path.exists(path) and util.ask_yn("Found %s cached data (%s).\nLoad this file?" % (name, path)):
        return util.read_json(path)
    return None


def find_bugs(queries):
    bug_data = []
    all_queries = []
    for q in queries:
        all_queries.extend(bzapi.parse_bugzilla_query(q))
    print "Running Bugzilla searches"
    for q in all_queries:
        sys.stdout.write('.')
        sys.stdout.flush()
        search_data = bzapi.search(q)
        for bug in search_data:
            if not bug in bug_data:
                bug_data.append(bug)
    sys.stdout.write('\nFinished running searches\n')
    sys.stdout.flush()
    return [x for x in bug_data if not is_skipable(x)]


def order_commits(repo_dir, requirements):
    commits = []
    for bug_id in requirements.keys():
        if requirements[bug_id].has_key('commits'):
            commits.extend(requirements[bug_id]['commits'])
    return git.sort_commits(repo_dir, commits, "master")


def uplift_bug(repo_dir, bug_id, commit, to_branches, from_branch="master"):
    """Uplift bug_id from branch to to_branches.  Return successful branches"""
    uplift_info = {'success': {},
                   'failure': []}
    for branch in to_branches:
        print "\n", "="*80
        print "Doing a cherry-pick for bug %s of commit %s to branch %s" % (bug_id, commit, branch)
        try:
            new_rev = git.cherry_pick(repo_dir, commit, branch, from_branch)
        except git.GitError:
            new_rev = None
        if new_rev:
            print "Success!"
            uplift_info['success'][branch] = new_rev
        else:
            print "Failure"
            uplift_info['failure'].append(branch)
    return uplift_info


def uplift(repo_dir, gaia_url, requirements, start_fresh=True):
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

    all_bugs = find_commits.for_all_bugs(repo_dir, requirements)
    with_commits = {}
    for bug_id in all_bugs.keys():
        if all_bugs[bug_id].has_key('commits'):
            with_commits[bug_id] = all_bugs[bug_id]

    util.write_json(requirements_file, with_commits)
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
        for commit in git.sort_commits(repo_dir, uplift_report[bug_id]['commits'], 'master'):
            if commit in uplift.keys():
                if not uplift_report[bug_id].has_key('uplift_status'):
                    uplift_report[bug_id]['uplift_status'] = {}
                u = uplift_report[bug_id]['uplift_status']
                u[commit] = copy.deepcopy(uplift[commit]['uplift_status'])
                failed_branches.extend([x for x in u[commit]['failure'] if x not in failed_branches])
                successful_branches.extend([x for x in u[commit]['success'].keys() if x not in successful_branches])
        # Because we might have multiple commits, we want to make sure that the list of successful branches
        # includes only those with *no* failing uplifts
        for i in range(len(successful_branches) - 1, -1, -1):
            if successful_branches[i] in failed_branches:
                del successful_branches[i]
        uplift_report[bug_id]['flags_to_set'] = branch_logic.flags_to_set(successful_branches)

    util.write_json(uplift_report_file, uplift_report)
    return uplift_report


def skip_bug(bug_id):
    if os.path.isfile(skip_bugs_file):
        data = util.read_json(skip_bugs_file)
    else:
        data=[]
    util.write_json(skip_bugs_file, sorted(set([int(bug_id)] + [int(x) for x in data])))


def is_skipable(bug_id):
    # This is a bad idea.  The program should really use integer bug ids everywhere
    _bi = int(bug_id)
    skip_bugs = util.read_json(skip_bugs_file)
    if not skip_bugs:
        skip_bugs = []
    for skip_bug in skip_bugs:
        if _bi == skip_bug:
            return True
    return False

def build_uplift_requirements(repo_dir, queries):
    bug_info = read_requirements("uplift information", requirements_file)
    if not bug_info:
        skip_bugs = util.read_json(skip_bugs_file)
        bug_info = {}
        bugs = dict([(x, bzapi.fetch_complete_bug(x)) for x in find_bugs(queries) if not x in skip_bugs])
        for bug_id in [x for x in sorted(bugs.keys()) if not is_skipable(x)]:
            bug = bugs[bug_id]
            needed_on = branch_logic.needed_on_branches(bug)
            if len(needed_on) == 0:
                continue
            b = bug_info[bug_id] = {}
            b['needed_on'] = needed_on
            b['already_fixed_on'] = branch_logic.fixed_on_branches(bug)
            b['summary'] = bug['summary']
        util.write_json(requirements_file, bug_info)
    return bug_info


def _display_push_info(push_info):
    for branch in push_info['branches'].keys():
        start, end = push_info['branches'][branch]
        print "%s: %s..%s" % (branch, start, end)


def push(repo_dir):
    branches = c.read_value('enabled_branches')
    preview_push_info = git.push(
        repo_dir, remote="origin",
        branches=branches, dry_run=True)
    print "This is what you'd be pushing: "
    _display_push_info(preview_push_info)
    prompt = "push, a branch name or cancel: "
    user_input = raw_input(prompt).strip()
    actual_push_info = None
    while True:
        if user_input == 'push':
            actual_push_info = git.push(
                repo_dir, remote="origin",
                branches=branches,
                dry_run=False)
            break
        elif user_input == 'cancel':
            print "Cancelling"
            break
        elif user_input in branches:
            print "Commits that will be pushed to %s on branch %s" % (preview_push_info['url'], user_input)
            print "="*80
            start, end = preview_push_info['branches'][user_input]
            git.git_op(['log', user_input, '--oneline', '%s..%s' % (start, end)], workdir=repo_dir)
            print "not done yet, would show log for %s" % user_input
        else:
            user_input = raw_input(prompt).strip()
    return actual_push_info


