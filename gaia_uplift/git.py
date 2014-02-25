"""This module is an ugly wrapper around the git operations needed"""

import os
import subprocess as sp
import shutil
import isodate
import re
import json
import traceback
import copy

import configuration as c

class GitError(Exception): pass

# TODO: Come up with a better name!
class GitNoop(GitError): pass

class PushFailure(GitError): pass

git_bin = 'git'
valid_id_regex = "[a-fA-F0-9]{7,40}"

def run_cmd(command, workdir, read_out=True, env=None, delete_env=None, **kwargs):
    """ Wrap subprocess in a way that I like.
    command: string or list of the command to run
    workdir: directory to do the work in
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
    if read_out:
        func = sp.check_output
    else:
        func = sp.check_call

    kwargs = copy.deepcopy(kwargs)
    kwargs['stderr'] = sp.PIPE
    if read_out:
        kwargs['stdout'] = sp.PIPE

    proc = sp.Popen(command, cwd=workdir, env=full_env, **kwargs)

    stdout, stderr = proc.communicate()

    with open("cmds.log", "ab+") as cmd_log:
        log_line = {
            'command': command,
            'cwd': os.getcwd(),
            'workdir': workdir,
            'env': env,
            'exit_code': proc.returncode,
            'stdout': stdout,
            'stderr': stderr
        }
        json.dump(log_line, cmd_log, indent=2)
        cmd_log.write(',\n')
        cmd_log.flush()

    if proc.returncode != 0:
        raise sp.CalledProcessError(proc.returncode, command, stdout)
    if read_out:
        return stdout
    return 0 # We can't get here without the return code being other than zero

def git_op(command, workdir=os.getcwd(), **kwargs):
    """ This function is a simple wrapper that might be used to make
    setting the path to git less obnoxious"""
    try:
        return run_cmd([git_bin] + command, workdir, **kwargs)
    except sp.CalledProcessError, e:
        raise GitError({'command': command,
                        'workdir': workdir,
                        'options': kwargs,
                        'super_exc': e,
                        'traceback': traceback.format_exc()})


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

def current_branch(repo_dir):
    cmd_out = git_op(["branch"], workdir=repo_dir)
    for line in [x.strip() for x in cmd_out.split('\n')]:
        if line[:2] == "* ":
            return line[2:]
    return None


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
    return git_op(["cat-file", "-t", o_id.strip()], workdir=repo_dir).strip()


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


def checkout(repo_dir, commitish=None, tracking=None, branch_name=None):
    cmd = ["checkout"]
    if tracking:
        cmd.extend(["-t", tracking])
    if branch_name:
        cmd.extend(["-b", branch_name])
    if commitish:
        cmd.append(commitish)
    git_op(cmd, workdir=repo_dir)


def merge(repo_dir, branch_from, strategy=None, strategy_options=None, ff_only=False, no_ff=False):
    cmd = ["merge"]
    if ff_only and no_ff:
        raise GitError("You're asking for a fast-forward merge that's not a fast-forward merge")
    if ff_only:
        cmd.append("--ff-only")
    if no_ff:
        cmd.append("--no-ff")
    if strategy:
        cmd.extend(["-s", strategy])
    if strategy_options:
        for opt in strategy_options:
            cmd.extend(["-X", opt])
    cmd.append(branch_from)
    git_op(cmd, workdir=repo_dir)


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
        raise GitError("commit %s is not on upstream branch %s" % (commit, upstream))
    elif commit_on_branch(repo_dir, commit, branch):
        raise GitNoop("trying to cherry-pick '%s' to '%s' which already contains it" % (commit, branch))
    else:
        command = ["cherry-pick", "-x"] # -x leaves some breadcrumbs
        master_num = determine_cherry_pick_master_number(repo_dir, commit, upstream)
        if master_num:
            command.append(master_num)
        command.append(commit)
        git_op(command, workdir=repo_dir)
    return get_rev(repo_dir)


def log(repo_dir, commitish, number=None, pretty=None):
    cmd = ["log", commitish]
    if number:
        cmd.append("-n%d" % number)
    if pretty:
        cmd.append("--pretty=%s" % pretty)

    return git_op(cmd, workdir=repo_dir)

def reset(repo_dir, id="HEAD", hard=True):
    command = ["reset"]
    if hard:
        command.append("--hard")
    command.append(id)
    return git_op(command, workdir=repo_dir)


def a_before_b(repo_dir, branch, commit_times, a, b):
    """Return True if a's commit time on branch is older than b's commit time on branch"""
    # commit_times is a dictionary that gets passed in by reference and is used to
    # cache the output of the time parsing logic.  it can be {}
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
    a_time = get_commit_time(a)
    b_time = get_commit_time(b)
    if a_time == b_time:
        raise Exception("Trying to compare two commit times that are the same %s and %s (%s)" % (a,b,a_time))
    return a_time < b_time



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
    return [x.strip() for x in git_op(["log", "-n1", "--pretty=%P", commit], workdir=repo_dir).split(' ')]


def push(repo_dir, remote="origin", branches=[], dry_run=True):
    """ Push code on branches to remote and return a dictionary like:
        {'url': 'repo.git',
         'branches': {'master': (first_commit, last_commit),
                      'other': (first_commit, last_commit)
                     }
        }
    """
    #(uplifting)jhford-air:~/b2g/uplifting $ git push --porcelain
    #STDERR:Counting objects: 51, done.
    #STDERR:Delta compression using up to 4 threads.
    #STDERR:Compressing objects: 100% (42/42), done.
    #STDERR:Writing objects: 100% (42/42), 4.64 KiB, done.
    #STDERR:Total 42 (delta 29), reused 0 (delta 0)
    #STDOUT:To git@github.com:jhford/uplift.git
    #STDOUT:	refs/heads/master:refs/heads/master	deb52cd..f46620e
    #STDOUT:Done
    command = ['push', '--porcelain']
    if dry_run:
        command.append('--dry-run')
    if remote:
        command.append(remote)
    command += branches
    try:
        output = git_op(command, workdir=repo_dir)
    except Exception as e:
        print e
        raise PushFailure("Failed to run git command '%s' to push" % command)
    lines = [x for x in output.split('\n') if x.strip() != '']
    if lines[-1].strip() != 'Done':
        raise PushFailure("Failed to complete push of '%s' to '%s'" % ("', '".join(branches), remote))
    push_data = {
        'branches':{},
        'url': lines[0].strip().lstrip('To ')
    }
    for push_item in lines[1:-1]:
        flag, ref_spec, rev_range = push_item.split('\t')
        if flag != ' ':
            continue
        local_branch, remote_branch = [x.lstrip('refs/heads/') for x in ref_spec.split(':')]
        first_commit, last_commit = rev_range.split('..')
        first_commit = get_rev(repo_dir, first_commit)
        last_commit = get_rev(repo_dir, last_commit)
        push_data['branches'][local_branch] = (first_commit, last_commit)
    return push_data


def recreate_branch(repo_dir, branch, remote="origin"):
    if branch in branches(repo_dir):
        git_op(["branch", "-D", branch], workdir=repo_dir)
    git_op(["checkout", "-t", "%s/%s" % (remote, branch), "-b", branch], workdir=repo_dir)


def _cache_dir(repo_dir):
    repo_dir_p, repo_dir_t = os.path.split(repo_dir.rstrip(os.sep))
    return os.path.join(repo_dir_p, ".%s.cache.git" % repo_dir_t)


def create_gaia(repo_dir, gaia_url):
    # These two lines are stupid.  They break subtlely when
    # repo_dir isn't an absolute path. 
    repo_dir_p = os.path.split(repo_dir.rstrip(os.sep))[0]
    cache_dir = _cache_dir(os.path.abspath(repo_dir))

    # Initialize or update the cached copy of gaia
    if not os.path.isdir(cache_dir):
        print "Initial clone of Gaia cache directory"
        git_op(["clone", "--mirror", gaia_url, cache_dir],
               workdir=os.path.split(cache_dir.rstrip(os.sep))[0])
    else:
        print "Fetching updates to Gaia cache directory"
        git_op(["fetch", "--all"], workdir=cache_dir)

    # Because we do all of the repository creation locally (i.e. cheaply), we don't
    # really want to risk having bad commits left around, so we delete the repo
    print "Deleting Gaia scratch directory"
    delete_gaia(repo_dir)

    # Let's create the working copy of gaia.  We want to clone it from the
    # cache, fix the remotes and create the remote references in the local
    # copy by fetching from the actual remote.  We fetch the actual remote's
    # references because we want to create a copy of gaia that doesn't need
    # to use the cached copy when pushing changes
    print "Cloning Gaia scratch from cache"
    git_op(["clone", "file://%s" % cache_dir, repo_dir], workdir=repo_dir_p)
    git_op(["remote", "rename", "origin", "cache"], workdir=repo_dir)
    git_op(["remote", "add", "origin", gaia_url], workdir=repo_dir)
    print "Fetching remote references"
    git_op(["fetch", "origin"], workdir=repo_dir)
    branches = c.read_value('repository.enabled_branches')
    for branch in branches + ['master']:
        recreate_branch(repo_dir, branch, remote="origin")


def delete_gaia(repo_dir):
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)


def update_gaia(repo_dir, gaia_url):
    if not os.path.exists(repo_dir):
        print "Gaia doesn't exist yet"
    cache_dir = _cache_dir(repo_dir)
    git_op(["fetch", "--all"], workdir=cache_dir)
    git_op(["fetch", "cache"], workdir=repo_dir)
    git_op(["fetch", "origin"], workdir=repo_dir)
    for branch in branch_logic.branches + ['master']:
        #recreate_branch(repo_dir, branch, remote="origin")
        git_op(["reset", "--hard", "HEAD"], workdir=repo_dir)
        git_op(["checkout", branch], workdir=repo_dir)
        git_op(["merge", "--ff-only", "%s/%s" % ("origin", branch)], workdir=repo_dir)
