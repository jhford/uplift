import sys
import copy
import re
import json
import subprocess as sp

import git
import util
import bzapi
import uplift
import branch_logic


# Let's steal the pattern that validates a sha1 as a valid
# commit id from our git logic
id_pattern = git.valid_id_regex

# These regexes *must* have a single named group:
#   * id: this is a direct commit id, do nothing further
#   * pr: this is a pull request number, look up the PR
_commit_regex = [
    "github.com/mozilla-b2g/gaia/commit/(?P<id>%s)" % id_pattern,
    "github.com/mozilla-b2g/gaia/pull/(?P<pr>\d*)"
]
commit_regex = [re.compile(x) for x in _commit_regex]


def guess_from_pr(repo_dir, upstream, pr_num):
    # Useful: https://api.github.com/repos/mozilla-b2g/gaia/pulls/7742
    #print "You should checkout Pull Request: %d" % pr_num
    return None


def guess_from_comments(repo_dir, upstream, comments):
    commits = {}
    pull_requests = []
    for c in comments:
        if not c.has_key('text') or c.get('text', None) == None or c.get('text', '') == '':
            continue
        for r in commit_regex:
            c_txt = c['text']
            matches = r.finditer(c_txt)
            for m in matches:
                d = m.groupdict()
                if d.has_key('id'):
                    commit_id = d['id']
                    if git.git_object_type(repo_dir, commit_id) == 'commit':
                        if git.get_rev(repo_dir, commit_id) and git.commit_on_branch(repo_dir, commit_id, upstream):
                            if not commits.has_key(commit_id):
                                commits[commit_id] = []
                            # The reason should include the person's real name!
                            reason = "%s made a comment which matched the pattern %s:\n%s\n%s" % (
                                c['creator']['name'], r.pattern, "-"*80, c_txt)

                            commits[commit_id].append(reason)
                elif d.has_key('pr'):
                    try:
                        pr_num = int(d['pr'], 10)
                    except ValueError:
                        pass

                    if not pr_num in pull_requests:
                        pull_requests.append(pr_num)

    for pr_num in pull_requests:
        guess_from_pr(repo_dir, upstream, pr_num)
    return commits


def guess_from_attachments(repo_dir, upstream, comments):
    return []


def guess_commit(repo_dir, upstream, bug):
    """I take a bug_id and scan the bug comments and attachements to see if I can find
    some valid commits.  I return a list of (commit, reason) doubles, where the commit
    is a string of what I think is the case and the reason is a human readable string
    explaining *why* the commit is likely"""
    guessed_commits = {}

    def merge(y):
        for k in y.keys():
            if not guessed_commits.has_key(k):
                guessed_commits[k] = []
            guessed_commits[k].extend(y[k])

    if bug.has_key('comments'):
        merge(guess_from_comments(repo_dir, upstream, bug['comments']))
    if bug.has_key('attachments'):
        merge(guess_from_comments(repo_dir, upstream, bug['attachments']))
    return guessed_commits


def open_bug_in_browser(bug_id):
    """I know how to open a bug for inspection"""
    if sys.platform == "darwin":
        git.run_cmd(["open", "https://bugzilla.mozilla.org/show_bug.cgi?id=%d" % int(bug_id)], workdir='.')
    elif sys.platform == "linux2":
        git.run_cmd(["firefox", "https://bugzilla.mozilla.org/show_bug.cgi?id=%d" % int(bug_id)], workdir='.')


def for_one_bug(repo_dir, bug_id, upstream):
    """ Given a bug id, let's find the commits that we care about.  Right now, make the hoo-man dooo eeeet"""
    commits=[]
    bug_data = bzapi.fetch_complete_bug(bug_id)
    guesses = guess_commit(repo_dir, upstream, bug_data)
    try:
        pass
    except Exception, e:
        # We *really* don't want to kill the program because of guessing.
        print "Guessing failed"
        guesses = {}


    def _list_commits():
        if len(commits) > 0:
            print "Commits entered:"
            for i in range(0, len(commits)):
                print "  %d) %s" % (i, commits[i])
        else:
            print "No commits entered"

    def _show_guesses():
        keys = guesses.keys()
        for i in range(0, len(keys)):
            print "  * guess-%d: %s" % (i+1, keys[i])
            print "    BECAUSE:"
            for reason in guesses[keys[i]]:
                for line in reason.split('\n'):
                    print "          %s" % line

    def _open_browser():
        open_bug_in_browser(bug_id)

    _open_browser()

    prompt = "Bug %s %%d commits\nEnter command: " % bug_id
    print "=" * 80
    print "Needed on: %s" % util.e_join(branch_logic.needed_on_branches(bug_data))
    print "Fixed on: %s" % util.e_join(branch_logic.fixed_on_branches(bug_data))
    print "Type one of"
    if len(guesses) > 0:
        _show_guesses()
    print "  * sha1 commit: add a raw commit number"
    print "  * skip: add a bug to the list of permanently skipped bugs"
    print "  * delete-all: remove all commits from this bug"
    print "  * browser: (re)open the bug in a browser"
    print "  * delete: enter the delete loop"

    user_input = raw_input(prompt % len(commits)).strip()

    guess_re = re.compile('^guess-(?P<guess>\d+)$')
    
    # This loop has gotten pretty disgusting.
    while user_input != 'done':
        if user_input == "list":
            _list_commits()
        elif user_input == "skip":
            print "Adding a bug to the skipped bug list means that you will never"
            print "see it again.  This is persisted between executions of this program"
            if util.ask_yn("Add bug to skipped bug list?"):
                uplift.skip_bug(bug_id)
            break
        elif user_input == "delete-all":
            commits = []
        elif len(guesses) > 0 and guess_re.match(user_input):
            guess_num = int(guess_re.match(user_input).group('guess'))
            
            if guess_num < 1 or guess_num > len(guesses.keys()):
                print "You are trying to use a guess that's invalid"
            else:
                guessed_commit = guesses.keys()[guess_num - 1]
                if git.valid_id(guessed_commit):
                    commits.append(guesses.keys()[guess_num - 1])
                else:
                    print "Guessed commit isn't valid"
        elif user_input == "browser":
            _open_browser()
        elif user_input == "delete":
            del_prompt = "Enter the number of the commit to delete, 'all' to clear the list or 'done' to end: "
            _list_commits()
            del_input = raw_input(del_prompt).strip()
            while del_input != 'done':
                if del_input == 'all':
                    commits = []
                    break
                else:
                    try:
                        n = int(del_input, 10)
                        valid_input = True
                    except ValueError:
                        print "Invalid input: %s" % del_input
                        valid_input = False
                    if valid_input:
                        if n >= 0 and n < len(commits):
                            del commits[n]
                        else:
                            print "You entered an index that's out of the range 0-%d" % len(commits)
                _list_commits()
                del_input = raw_input(del_prompt).strip()
        elif git.valid_id(user_input):
            if not git.commit_on_branch(repo_dir, user_input, upstream):
                print "Commit %s is not on the upstream branch '%s'" % (user_input, upstream)
                _list_commits()
            else:
                try:
                    full_rev = git.get_rev(repo_dir, id=user_input)
                    print "appending %s" % full_rev
                    commits.append(full_rev)
                    _list_commits()
                except sp.CalledProcessError, e:
                    print "This sha1 commit id (%s) is valid but not found in %s" % (user_input, repo_dir)
        else:
            print "This is not a sha1 commit id: %s" % user_input
        user_input = raw_input(prompt % len(commits)).strip()
    return commits


def for_all_bugs(repo_dir, requirements, upstream="master"):
    # Let's see if we have any commits in the req file.
    any_bug_has_commits = False
    bugs_without_commits = []
    for bug_id in requirements:
        if len(requirements[bug_id].get('commits', [])) > 0:
            any_bug_has_commits = True
        else:
            bugs_without_commits.append(bug_id)

    if any_bug_has_commits:
        print "Some bugs in this requirements file already have commits."
        # reuse is use the existing commits, don't ask for more.
        # add is use the existing commits for bugs that have no commits, ignore others
        # delete will remove the commits from the requirements dictionary
        prompt = "Enter 'reuse', 'add' or 'delete': "
        user_input = raw_input(prompt).strip()
        while user_input not in ('reuse', 'add', 'delete'):
            user_input = raw_input(prompt).strip()
        
        if user_input == 'reuse':
            bugs_to_find = [] # just use what's in the file
        elif user_input == 'add':
            bugs_to_find = bugs_without_commits # Only ask for commits for commit-less bugs
        elif user_input == 'delete':
            # Delete the commits that are in the requirements file
            for bug_id in requirements.keys():
                del requirements[bug_id]['commits']
            uplift.write_cache_file(requirements, uplift.requirements_file)
            bugs_to_find = requirements.keys()
        else:
            raise Exception("Huh?")
    else:
        bugs_to_find = requirements.keys()

    pruned_bugs_to_find = [x for x in bugs_to_find if not uplift.is_skipable(x)]
    j=0
    for bug_id in sorted(pruned_bugs_to_find):
        j+=1
        print "=" * 80
        print "Bug %d of %d" % (j, len(pruned_bugs_to_find))
        requirements[bug_id]['commits'] = for_one_bug(repo_dir, bug_id, upstream)
        uplift.write_cache_file(requirements, uplift.requirements_file)
    return requirements


