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


# Should be smarter about these cache files and either manage them in sets
# or use a single file which contains *all* the information only ever added to
requirements_cache_file = os.path.abspath("requirements.json")
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
        print "\n", "="*80
        print "Doing a cherry-pick for bug %s of commit %s to branch %s" % (bug_id, commit, branch)
        new_rev = git.cherry_pick(repo_dir, commit, branch, from_branch)
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

    with_commits = find_commits.for_all_bugs(repo_dir, requirements)
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

    write_cache_file(uplift_report, uplift_report_file)
    return uplift_report


def skip_bug(bug_id):
    with open('skip_bugs.json', 'rb+') as f:
        data=json.load(f)
        new_data = [int(bug_id)] + [int(x) for x in data]
        f.seek(0)
        json.dump(sorted(data), f, indent=2)


def is_skipable(bug_id):
    with open('skip_bugs.json', 'rb+') as f:
        data = json.load(f)
    return bug_id in data

def build_uplift_requirements(repo_dir, queries):
    bug_info = read_cache_file("uplift information", requirements_cache_file)
    if not bug_info:
        bug_info = {}
        bugs = dict([(x, bzapi.fetch_bug(x)) for x in find_bugs(queries)])
        for bug_id in [x for x in bugs.keys() if not is_skipable(x)]:

            b = bug_info[bug_id] = {}
            bug = bugs[bug_id]
            b['needed_on'] = branch_logic.needed_on_branches(bug)
            b['already_fixed_on'] = branch_logic.fixed_on_branches(bug)
            b['summary'] = bug['summary']
        write_cache_file(bug_info, requirements_cache_file)
    return bug_info


def _display_push_info(push_info):
    pass


def push(repo_dir):
    preview_push_info = git.push(
        repo_dir, remote="origin",
        branches=branch_logic.branches, dry_run=True)
    print "This is what you'd be pushing:"
    _display_push_info(preview_push_info)
    prompt = "push, a branch name or cancel: "
    user_input = raw_input(prompt).strip()
    actual_push_info = None
    while True:
        if user_input == 'push':
            actual_push_info = git.push(
                repo_dir, remote="origin",
                branches=branch_logic.branches,
                dry_run=False)
            break
        elif user_input == 'cancel':
            print "Cancelling"
            break
        elif user_input in branch_logic.branches:
            print "not done yet, would show log for %s" % user_input
        else:
            user_input = raw_input(prompt).strip()
    return actual_push_info


