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

gaia_path = os.path.abspath(os.path.join(os.getcwd(), 'uplift-gaia'))
gaia_url = "github.com:mozilla-b2g/gaia.git"
query_file = os.path.abspath("uplift_queries.dat")


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
        print reporting.display_uplift_requirements(bugs)
    elif cmd == 'uplift':
        requirements = build_uplift_requirements(gaia_path, queries)
        print "\n\nUplift requirements:"
        print reporting.display_uplift_requirements(requirements)
        uplift_report = uplift(gaia_path, requirements)
        print reporting.display_uplift_report(uplift_report)
        print reporting.display_uplift_comments(gaia_path, uplift_report)







