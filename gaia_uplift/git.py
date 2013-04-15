"""This module is an ugly wrapper around the git operations needed"""

import os
import subprocess as sp
import shutil
import isodate
import re
import json

import branch_logic


valid_id_regex = "[a-fA-F0-9]{7,40}"

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
    return re.match("^%s$" % valid_id_regex, id) != None


def _parse_branches(cmd_out):
    branches=[]
    for line in [x.strip() for x in cmd_out.split('\n')]:
        if line == '':
            continue
        elif line[:2] == "* ":
            branches.append(line[2:])
        else:
            branches.append(line)
    return branches


def branches(repo_dir):
    cmd_out = git_op(["branch"], workdir=repo_dir)
    return _parse_branches(cmd_out)


def commit_on_branch(repo_dir, commit, branch):
    """ Determine if commit is on a local branch"""
    obj_type = git_object_type(repo_dir, commit)
    if obj_type != 'commit':
        print "WARNING: %s is not a commit, rather a %s" % (commit, obj_type)
    try:
        cmd_out = git_op(["branch", "--contains", commit], workdir=repo_dir)
    except sp.CalledProcessError, e:
        return False
    if branch in _parse_branches(cmd_out):
        return True
    else:
        return False


def git_object_type(repo_dir, o_id):
    return git_op(["cat-file", "-t", o_id], workdir=repo_dir).strip()



def determine_cherry_pick_master_number(repo_dir, commit, upstream):
    parents = find_parents(repo_dir, commit)
    if len(parents) > 1:
        # There is a bug here where the parent_number is not set if the commit is not
        # on the 'upstream' branch.  This should raise an exception that's not about
        # using an unreferenced variable
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
    # TODO: Instead of returning the original commit, the new commit or None, we should
    # return a tuple of (outcome, new_or_same_commit_or_None)
    reset(repo_dir)
    git_op(["checkout", branch], workdir=repo_dir)
    # If the branch already has this commit, we don't want to re-cherry-pick it
    # but instead would like to return the original commit
    if not commit_on_branch(repo_dir, commit, upstream):
        print "Commit '%s' is not on the branch '%s' which we are using as upstream" % (commit, upstream)
        return None
    elif commit_on_branch(repo_dir, commit, branch):
        print "Commit '%s' is already on branch '%s'" % (commit, branch)
        return commit
    else:
        command = ["cherry-pick", "-x"] # -x leaves some breadcrumbs
        master_num = determine_cherry_pick_master_number(repo_dir, commit, upstream)
        if master_num:
            command.append(master_num)
        command.append(commit)
        try:
            git_op(command, workdir=repo_dir)
        except sp.CalledProcessError, e:
            git_op(["status"])
            git_op(["diff"])
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
        # This feels a little heavy handed.  If I want this logic to stay, it should
        # be something that the caller wants
        #else:
        #    raise Exception("commit %s is in the list of bugs to sort twice!" % commit)
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


def recreate_branch(repo_dir, branch, remote="origin"):
    if branch in branches(repo_dir):
        git_op(["branch", "-D", branch], workdir=repo_dir)
    git_op(["checkout", "-t", "%s/%s" % (remote, branch), "-b", branch], workdir=repo_dir)


def create_gaia(repo_dir, gaia_url):
    repo_dir_p = os.path.split(repo_dir.rstrip(os.sep))[0]
    # cache dir should really be .%(repo_dir)s.cache.git
    cache_dir = os.path.join(repo_dir_p, ".gaia.cache.git")

    # Initialize or update the cached copy of gaia
    if not os.path.isdir(cache_dir):
        git_op(["clone", "--mirror", gaia_url, cache_dir],
               workdir=os.path.split(cache_dir.rstrip(os.sep))[0])
    else:
        git_op(["fetch", gaia_url], workdir=cache_dir)

    # Because we do all of the repository creation locally (i.e. cheaply), we don't
    # really want to risk having bad commits left around, so we delete the repo
    delete_gaia(repo_dir)

    # Let's create the working copy of gaia.  We want to clone it from the
    # cache, fix the remotes and create the remote references in the local
    # copy by fetching from the actual remote.  We fetch the actual remote's
    # references because we want to create a copy of gaia that doesn't need
    # to use the cached copy when pushing changes
    git_op(["clone", "file://%s" % cache_dir, repo_dir], workdir=repo_dir_p)
    git_op(["remote", "rename", "origin", "cache"], workdir=repo_dir)
    git_op(["remote", "add", "origin", gaia_url], workdir=repo_dir)
    git_op(["fetch", "origin"], workdir=repo_dir)
    for branch in branch_logic.branches + ['master']:
        recreate_branch(repo_dir, branch, remote="origin")


def delete_gaia(repo_dir):
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)
