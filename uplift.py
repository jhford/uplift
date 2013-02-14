#!/usr/bin/env python
import sys, os
import subprocess as sp
import urllib
import csv
import re
import json
import datetime
import isodate

default_bug_query = "https://bugzilla.mozilla.org/buglist.cgi?bug_status=RESOLVED;bug_status=VERIFIED;chfield=resolution;chfieldfrom=2013-01-18;chfieldto=Now;chfieldvalue=FIXED;field0-0-0=cf_status_b2g18;field0-1-0=component;field1-0-0=flagtypes.name;field1-0-1=cf_blocking_b2g;list_id=5485185;query_format=advanced;type0-0-0=nowordssubstr;type0-1-0=substring;type1-0-0=substring;type1-0-1=equals;value0-0-0=fixed%20verified;value0-1-0=Gaia;value1-0-0=approval-gaia-v1%2B;value1-0-1=tef%2B;query_based_on=;columnlist=bug_severity%2Cpriority%2Cbug_status%2Cresolution%2Cshort_desc%2Ccf_blocking_b2g%2Ccf_tracking_b2g18%2Ccf_status_b2g18;ctype=csv"


def fetch_bugs(query):
    """Based on a bugzilla search query, fetch the bugs as a CSV list
    and return a table of the search results"""
    data = []
    # We only know how to process CSV return values
    if not 'ctype=csv' in query:
        query = query + ";ctype=csv"
    print "Fetching CSV bug list"
    csvdata = urllib.urlopen(query)
    reader = csv.reader(csvdata)
    row = reader.next()
    headers = list(row)
    for row in reader:
        row_data = {}
        for cell in range(0, len(row)):
            row_data[headers[cell]] = row[cell]
        data.append(row_data)
    csvdata.close
    print "Fetched CSV bug list"
    return data


def determine_uplift_destinations(bugs):
    """ Fetch a list of bugs and pick out relevant information into a bug information table that is returned.
    This is where the bugzilla flags turn into a list of branches to land on."""

    # TODO: This function should probably look at the status-b2g18 and status-b2g18-v1.0.0 and only include branches
    #       that are not set to 'fixed'.  This flags are in the json response as 'cf_status_b2g18' and 'cf_status_b2g18_1_0_0'

    bug_info = {}

    for bug in bugs:
        bug_info[bug['bug_id']] = {}
        bug_info[bug['bug_id']]['branches'] = branches = []
        bug_info[bug['bug_id']]['summary'] = bug['short_desc']
        print "="*80
        print "Fetching bug data for %d -- %s" % (int(bug['bug_id']), bug['short_desc'])
        bug_data = json.loads(urllib.urlopen("https://api-dev.bugzilla.mozilla.org/1.2/bug/%s" % bug['bug_id']).read())
        if bug_data['cf_blocking_b2g'] == 'tef+':
            branches.extend(['v1-train', 'v1.0.0'])
        elif bug_data['cf_blocking_b2g'] == 'shira+':
            branches.extend(['v1-train', 'v1.0.1'])
        elif bug_data['cf_blocking_b2g'] == 'leo+':
            branches.extend(['v1-train', 'v1.1.0'])
        else:
            for attachment in bug_data['attachments']:
                for flag in attachment.get('flags', []):
                    if flag['name'] == "approval-gaia-v1" and flag['status'] == '+':
                        branches.append('v1-train')
                        break # We only want to add one v1-train branch to the list of branches
        if len(branches) > 0:
            print "Bug %d needs to be uplifted to:" % int(bug['bug_id'])
            print "\n".join([" * %s" % x for x in branches])
        else:
            print "Bug %d does not need any uplifts" % int(bug['bug_id'])
    return bug_info


def find_commits_for_bug(repo_dir, bug):
    """ Given a bug id, let's find the commits that we care about.  Right now, make the hoo-man dooo eeeet"""
    sp.call(["open", "https://bugzilla.mozilla.org/show_bug.cgi?id=%d" % int(bug)])
    # TODO:  This function should be smarter.  It should scan the bug comments and attachements and 
    #        see if it can find sha1 sums which point to the master branch commit information.  
    #        This function should also take a 'from_branch' parameter to figure out which branch
    #        the changes are coming from
    commits=[]
    prompt = "Type in a commit that is needed for %d or 'done' to end: " % int(bug)
    user_input = raw_input(prompt).strip()
    while user_input != 'done':
        if re.match('^[a-fA-F0-9]{7,40}$', user_input):
            try:
                full_rev = git_op(["rev-parse", user_input], workdir=repo_dir).strip()
                print "appending %s to the list of revisions to use" % full_rev
                commits.append(full_rev)
            except sp.CalledProcessError, e:
                print "This sha1 commit id (%s) is valid but not found in %s" % (user_input, repo_dir)
        else:
            print "This is not a sha1 commit id: %s" % user_input
        user_input = raw_input(prompt).strip()
    return commits


def find_all_commits(repo_dir):
    """ This function finds all the commits that are needed in this uplift"""
    all_bugs = fetch_bugs(default_bug_query)
    bugs_to_uplift = determine_uplift_destinations(all_bugs)
    for bug in bugs_to_uplift.keys():
        commits = find_commits_for_bug(repo_dir, bug)
        bugs_to_uplift[bug]['commits'] = commits
    return bugs_to_uplift


def run_cmd(command, workdir, inc_err=False, read_out=True, env=None, delete_env=None, **kwargs):
    """ Wrap subprocess in a way that I like.
    command: string or list of the command to run
    workdir: directory to do the work in
    inc_err: include stderr in the output string returned
    read_out: decide whether we're going to want output returned or printed
    env: add this dictionary to the default environment
    delete_env: delete these environment keys"""
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    if delete_env:
        for d in delete_env:
            if full_env.has_key(d):
                del full_env[d]
    if inc_err:
        kwargs = kwargs.copy()
        kwargs['stdout'] = sp.STDOUT
    if read_out:
        func = sp.check_output
    else:
        func = sp.check_call
    return func(command, cwd=workdir, env=full_env, **kwargs)


def git_op(command, workdir=os.getcwd(), inc_err=False, **kwargs):
    """ This function is a simple wrapper that might be used to make
    setting the path to git less obnoxious"""
    return run_cmd(['git'] + command, workdir, inc_err, **kwargs)


def get_rev(repo_dir):
    """Get the full sha1 commit id of a git repository"""
    return git_op(["rev-parse", "HEAD"], workdir=repo_dir).strip()


def commit_on_branch(repo_dir, commit, branch):
    """ Determine if commit is on a local branch"""
    cmd_out = git_op(["branch", "--contains", commit], workdir=repo_dir)
    for line in cmd_out.split('\n'):
        if line.strip() == branch:
            return True
    return False


def cherry_pick(repo_dir, commit, branch, upstream='master'):
    """Perform a cherry pick of 'commit' from 'branch'.  If there is more than
    one parent for the commit, this function takes the first commit on the 'upstream'
    branch, defaulting to master, and uses it as the parent number to pass to
    git cherry-pick's -m parameter"""
    git_op(["checkout", branch], workdir=repo_dir)
    command = ["cherry-pick", "-x"] # -x leaves some breadcrumbs
    parents = find_parents(repo_dir, commit)
    if len(parents) > 1:
        for i in range(0, len(parents)):
            if commit_on_branch(repo_dir, commit, upstream):
                parent_number = i + 1
                break
        command.append("-m%d" % parent_number)
    command.append(commit)
    git_op(command, workdir=repo_dir)
    return get_rev(repo_dir)


def a_before_b(repo_dir, branch, a, b):
    """Return True if a's commit time on branch is older than b's commit time on branch"""
    def fix_git_timestamp(timestamp):
        """Yay git for generating non-ISO8601 datetime stamps.  Git generates, e.g.
        2013-01-29 16:06:52 -0800 but ISO8601 would be 2013-01-29T16:06:52-0800"""
        as_list = list(timestamp)
        as_list[10] = 'T'
        del as_list[19]
        return "".join(as_list)
    def get_commit_time(commit):
        time_from_git = git_op(["log", "--branches=%s" % branch, "-n1", commit, "--pretty=%ci"], workdir=repo_dir)
        return isodate.parse_datetime(fix_git_timestamp(time_from_git))
    a_time = get_commit_time(a)
    b_time = get_commit_time(b)
    return a < b


def sort_commits(git_dir, commits, branch):
    """I sort a list of commits based on when they appeared on a branch"""
    commits = commits[:]
    no_swaps = False
    while not no_swaps:
        no_swaps = True
        for i in range(1, len(commits)):
            if not a_before_b(git_dir, branch, commits[i-1], commits[i]):
                tmp = commits[i-1]
                commits[i-1] = commits[i]
                commits[i] = tmp
                no_swaps = False
    return commits


# TODO: Make this function more generic because I want to use it elsewhere
def transpose_commits(bug_dict):
    """ Take a dictionary that's bug indexed and turn it into a commit indexed one"""
    commit_indexed = {}
    for bug_id in bug_dict.keys():
        for commit in bug_dict[bug_id]['commits']:
            commit_indexed[commit] = {'bug_id': bug_id,
                                      'summary': bug_dict[bug_id]['summary'],
                                      'branches': bug_dict[bug_id]['branches']}
    return commit_indexed



def find_parents(repo_dir, commit):
    """Return a list of commit ids that are parents to 'commit'"""
    return git_op(["log", "-n1", "--pretty=%P", commit], workdir=repo_dir).split(' ')


def merge_comment(repo_dir, commit, branches):
    """Given a commit and a list of branches, generate and return a simple bash script that
    could be used to resolve the merge conflict"""
    comment = "cd gaia\n"
    comment += "git checkout %s\n" % branches[0]
    if len(find_parents(repo_dir, commit)) > 1:
        comment += "git cherry-pick -x -m1 %s\n" % commit
    else:
        comment += "git cherry-pick -x %s\n" % commit
    comment += "<resolve merge conflict>\n"
    for branch in range(1, len(branches)):
        comment += "git checkout %s\n" % branches[branch]
        comment += "git cherry-pick -x $(git log --pretty=%%H -n1 %s)\n" % branches[branch-1]
    return comment

# Below here is butt'turble


# Too lazy to use optparse or argparse
gaia_repo = os.path.abspath("gaia")
if not os.path.isdir(gaia_repo):
    print >>sys.stderr, "ERROR: Where is gaia?"
    exit(1)


load_file = False
if os.path.isfile("bug_data.json"):
    answer = raw_input("I found some cached data, use it? [Y/n]: ").strip()
    if answer.lower() == "y":
        load_file = True

if load_file:
    with open("bug_data.json", "r") as datafile:
        commit_indexed = json.load(datafile)
else:
    commit_indexed = transpose_commits(find_all_commits(gaia_repo))

with open("bug_data.json", "w+") as output:
    json.dump(commit_indexed, output, indent=2)


sorted_commit_indexed_keys = sort_commits(gaia_repo, commit_indexed.keys(), 'master')

uplifts = []
failures = []
for commit in sorted_commit_indexed_keys:
    for branch in commit_indexed[commit]['branches']:
        print "Trying to uplift %s (%s) onto %s" % (commit_indexed[commit]['bug_id'],
                                                    commit, branch)
        if commit_on_branch(gaia_repo, commit, branch):
            print "%s is already on %s" % (commit, branch)
        else:
            try:
                new_commit = cherry_pick(gaia_repo, commit, branch)
                uplifts.append((commit_indexed[commit]['bug_id'], branch, new_commit))
            except sp.CalledProcessError, e:
                print "Failed to cherry pick %s onto %s" % (commit, branch)
                git_op(["reset", "--hard", "HEAD"], workdir=gaia_repo)
                failures.append((commit, commit_indexed[commit]['bug_id'], branch))

bug_comments = {}
for bug_id, branch, new_commit in uplifts:
    if not bug_comments.has_key(bug_id):
        bug_comments[bug_id] = []
    bug_comments[bug_id].append((branch, new_commit))

for bug in bug_comments.keys():
    print "Comment for bug %s\n%s\n%s" % (bug, "="*80, "\n".join(["%s: %s" % x for x in bug_comments[bug]]))

bug_merge_comments = {}
for commit, bug_id, branch in failures:
    if not bug_merge_comments.has_key(commit):
        bug_merge_comments[commit] = {}
        bug_merge_comments[commit]['bug_id'] = bug_id
        bug_merge_comments[commit]['branches'] = [branch]
    else:
        bug_merge_comments[commit]['branches'] += [branch]


for commit in bug_merge_comments.keys():
    bug_id = bug_merge_comments[commit]['bug_id']
    branches = bug_merge_comments[commit]['branches']
    ordered_branches = []
    for i in ('v1-train', 'v1.1.0', 'v1.0.1', 'v1.0.0'):
        if i in branches:
            ordered_branches.append(i)
    print "Comment for bug %s\n%s\nThis commit does not apply cleanly to %s.  If this patch depends on another bug, please comment here and I will retry when that bug is approved to land on all branches that this bug needs to land on.  If the merge conflict needs to be resolved by hand, the following commands could be a useful starting point:\n\n%s" % \
            (bug_id, "="*80, ', '.join(ordered_branches), merge_comment(gaia_repo, commit, ordered_branches))



# TODO:
# need to be able to exclude bugs
# need to generate bug comment
# Figure out why there are newlines on the commits
# figure out better sorting algorithm
# figure out dependencies if they are set
