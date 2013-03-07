"""This module is an ugly wrapper around the git operations needed"""

import os
import subprocess as sp
import shutil
import isodate
import re
import json

import branch_logic


#XXX UGLY HACK OMG!
cmd_log=open("cmds.log", "wb+")

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
    print >> cmd_log, "command: %s, workdir=%s" % (command, workdir)
    return func(command, cwd=workdir, env=full_env, **kwargs)

def git_op(command, workdir=os.getcwd(), inc_err=False, **kwargs):
    """ This function is a simple wrapper that might be used to make
    setting the path to git less obnoxious"""
    return run_cmd(['git'] + command, workdir, inc_err, **kwargs)


def get_rev(repo_dir, id='HEAD'):
    """Get the full sha1 commit id of a git repository"""
    return git_op(["rev-parse", id], workdir=repo_dir).strip()


def show(repo_dir, id='HEAD', template="oneline"):
    return git_op(["show", id, "--pretty=%s" % template], workdir=repo_dir).strip()

def valid_id(id):
    return re.match("^[a-fA-F0-9]{7,40}$", id) != None


def commit_on_branch(repo_dir, commit, branch):
    """ Determine if commit is on a local branch"""
    try:
        cmd_out = git_op(["branch", "--contains", commit], workdir=repo_dir)
    except sp.CalledProcessError, e:
        return False
    for line in [x.strip() for x in cmd_out.split('\n')]:
        if line == branch: # Simple case
            return True
        # git branch shows current branch with "*  $branch".  We want to make sure
        # that if we're going to strip the "* " off, that we only do it when it's
        # definately "* " and not some other unexpected sequence
        if line[:2] == "* " and line[2:] == branch:
            return True
    return False


def determine_cherry_pick_master_number(repo_dir, commit, upstream):
    parents = find_parents(repo_dir, commit)
    if len(parents) > 1:
        for i in range(0, len(parents)):
            if commit_on_branch(repo_dir, parents[i], upstream):
                parent_number = i + 1
                break
        return "-m%d" % parent_number
    else:
        return None


def cherry_pick(repo_dir, commit, branch, upstream='master'):
    """Perform a cherry pick of 'commit' from 'branch'.  If there is more than
    one parent for the commit, this function takes the first commit on the 'upstream'
    branch, defaulting to master, and uses it as the parent number to pass to
    git cherry-pick's -m parameter"""
    reset(repo_dir)
    git_op(["checkout", branch], workdir=repo_dir)
    command = ["cherry-pick", "-x"] # -x leaves some breadcrumbs
    master_num = determine_cherry_pick_master_number(repo_dir, commit, upstream)
    if master_num:
        command.append(master_num)
    command.append(commit)
    try:
        git_op(command, workdir=repo_dir)
    except sp.CalledProcessError, e:
        return None
    return get_rev(repo_dir)


def reset(repo_dir, id="HEAD", hard=True):
    command = ["reset"]
    if hard:
        command.append("--hard")
    command.append(id)
    return git_op(command, workdir=repo_dir)


def a_before_b(repo_dir, branch, commit_times, a, b):
    """Return True if a's commit time on branch is older than b's commit time on branch"""
    def fix_git_timestamp(timestamp):
        """Yay git for generating non-ISO8601 datetime stamps.  Git generates, e.g.
        2013-01-29 16:06:52 -0800 but ISO8601 would be 2013-01-29T16:06:52-0800"""
        as_list = list(timestamp)
        as_list[10] = 'T'
        del as_list[19]
        return "".join(as_list)
    def get_commit_time(commit):
        # This value should be cached
        if commit_times.has_key(commit):
            git_time = commit_times[commit]
        else:
            git_time = git_op(["log", "--branches=%s" % branch, "-n1", commit, "--pretty=%ci"], workdir=repo_dir).strip()
            commit_times[commit] = git_time
        return isodate.parse_datetime(fix_git_timestamp(git_time))
    if a == b:
        raise Exception("Trying to compare two commits that are the same")
    a_time = get_commit_time(a)
    b_time = get_commit_time(b)
    return a < b



def sort_commits(repo_dir, commits, branch):
    """I sort a list of commits based on when they appeared on a branch"""
    commit_times = {}
    c = []
    for commit in commits:
        if not commit in c:
            c.append(commit)
        else:
            raise Exception("commit %s is in the list of bugs to sort twice!" % commit)
    commits = c
    no_swaps = False
    while not no_swaps:
        no_swaps = True
        for i in range(1, len(commits)):
            if not a_before_b(repo_dir, branch, commit_times, commits[i-1], commits[i]):
                tmp = commits[i-1]
                commits[i-1] = commits[i]
                commits[i] = tmp
                no_swaps = False
    return commits


def find_parents(repo_dir, commit):
    """Return a list of commit ids that are parents to 'commit'"""
    return git_op(["log", "-n1", "--pretty=%P", commit], workdir=repo_dir).split(' ')


def _determine_gaia_cache_dir(repo_dir):
    return os.path.join(os.path.split(repo_dir.rstrip(os.sep))[0], ".gaia.cache.git")

def update_gaia(repo_dir, gaia_url):
    cache_dir = _determine_gaia_cache_dir(repo_dir)
    git_op(["fetch", "--all"], workdir=cache_dir)
    git_op(["fetch", "--all"], workdir=repo_dir)
    for b in branch_logic.branches:
        git_op(["checkout", "-t", "origin/%s"%b, "-b", b], workdir=repo_dir)
        git_op(["merge", "origin/%s" % b], workdir=repo_dir)
    git_op(["checkout", "master"], workdir=repo_dir)
    git_op(["merge", "origin/master"], workdir=repo_dir)

def create_gaia(repo_dir, gaia_url):
    cache_dir = _determine_gaia_cache_dir(repo_dir)
    if not os.path.isdir(cache_dir):
        git_op(["clone", "--mirror", gaia_url, cache_dir],
               workdir=os.path.split(cache_dir.rstrip(os.sep))[0])
    else:
        git_op(["fetch", gaia_url], workdir=cache_dir)
    git_op(["clone", "file://%s" % cache_dir, repo_dir], workdir=os.path.split(repo_dir.rstrip(os.sep))[0])
    git_op(["remote", "rename", "origin", "cache"], workdir=repo_dir)
    git_op(["remote", "add", "origin", gaia_url], workdir=repo_dir)
    update_gaia(repo_dir, gaia_url)

def delete_gaia(repo_dir):
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)
