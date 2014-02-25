#!/usr/bin/env python
""" This is a new version of uplift.py"""
import os
import sys

import copy
import json
import time

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
uplift_dated_file = os.path.abspath("uplift_outcome_%s.json" % util.time_str())
push_info_file = os.path.abspath("uplift_info_%s.json" % util.time_str())
skip_bugs_file = os.path.abspath("skip_bugs.json")


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


def uplift_commit(repo_dir, commit, to_branches, from_branch="master"):
    uplift_info = {'success': {},
                   'failure': []}
    for branch in to_branches:
        try:
            new_rev = git.cherry_pick(repo_dir, commit, branch, from_branch)
        except git.GitNoop:
            # TODO: Do something smarter here
            new_rev = commit
        except git.GitError:
            new_rev = None

        if new_rev:
            uplift_info['success'][branch] = new_rev
        else:
            uplift_info['failure'].append(branch)
    return uplift_info


def uplift(repo_dir, gaia_url, requirements):
    # Setup stuff
    t=util.time_start()
    print "Updating Gaia"
    git.create_gaia(repo_dir, gaia_url) # This is sadly broken
    print "Created Gaia in %0.2f seconds" % util.time_end(t)

    # Determining what needs to be uplifted
    with_commits = {}
    for bug_id in requirements.keys():
        if requirements[bug_id].has_key('commits'):
            with_commits[bug_id] = requirements[bug_id]

    ordered_commits = order_commits(repo_dir, with_commits)

    uplift = dict([(x, {}) for x in ordered_commits])

    # Uplifting
    for commit in ordered_commits:
        needed_on = []
        for bug_id in with_commits.keys():
            if commit in with_commits[bug_id]['commits']:
                for i in with_commits[bug_id]['needed_on']:
                    if not i in needed_on:
                        needed_on.append(i)
        print "\n", "="*80
        print "Attempting to uplift %s commit to %s" % (commit, util.e_join(needed_on))
        uplift[commit]['needed_on'] = needed_on
        result = uplift_commit(repo_dir, commit, needed_on)
        print "Sucess on %s" % util.e_join(result['success'].keys())
        print "Failure on %s" % util.e_join(result['failure'])
        uplift[commit]['uplift_status'] = result

    uplift_report = copy.deepcopy(with_commits)

    # Determinging which commits belong to which bugs
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

    util.write_json(uplift_dated_file, uplift_report)
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

def build_uplift_requirements(repo_dir):
    if os.path.exists(requirements_file) and util.ask_yn("Found existing requirements. Should they be used?"):
        bug_info = util.read_json(requirements_file)
    else:
        bug_info = {}
        enabled_branches = c.read_value('repository.enabled_branches')
        all_queries = c.read_value('queries')
        queries = []
        for branch in enabled_branches:
            queries.extend(all_queries[branch])

        bugs = [x for x in find_bugs(queries) if not is_skipable(x)]
        print "Fetching bug data"
        for bug_id in bugs:
            if is_skipable(bug_id):
                continue
            bug = bzapi.fetch_complete_bug(bug_id)
            print "+",
            needed_on = branch_logic.needed_on_branches(bug)
            if len(needed_on) == 0:
                continue
            b = bug_info[bug_id] = {}
            b['needed_on'] = needed_on
            b['already_fixed_on'] = branch_logic.fixed_on_branches(bug)
            b['summary'] = bug['summary']
        print "\nFinished fetching bug data"
        util.write_json(requirements_file, bug_info)
    return bug_info


def _display_push_info(push_info):
    for branch in push_info['branches'].keys():
        start, end = push_info['branches'][branch]
        print "  * %s: %s..%s" % (branch, start[:7], end[:7])


def push(repo_dir):
    branches = c.read_value('repository.enabled_branches')
    preview_push_info = git.push(repo_dir, remote="origin", branches=branches, dry_run=True)
    print "If you push, you'd be pushing: "
    _display_push_info(preview_push_info)
    if not util.ask_yn('Do you wish to push?'):
        return None
    for i in range(5):
        try:
            rv = git.push(repo_dir, remote="origin", branches=branches, dry_run=False)
            util.write_json(push_info_file, rv)
            print "Push attempt %d worked" % int(i+1)
            return rv
        except:
            print "Push attempt %d failed" % int(i+1)
    raise git.PushFailure("remote %s branches %s" % (remote, util.e_join(branches)))

