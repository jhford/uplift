import sys
import copy
import re
import json

import git
import util
import bzapi


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
    # Useful: https://api.github.com/repos/mozilla-b2g/gaia/pulls/7742, look for a merge_commit_sha key
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
                    print "Found a guess"
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


def guess_commit(repo_dir, upstream, bug_id):
    """I take a bug_id and scan the bug comments and attachements to see if I can find
    some valid commits.  I return a list of (commit, reason) doubles, where the commit
    is a string of what I think is the case and the reason is a human readable string
    explaining *why* the commit is likely"""
    bug_data = bzapi.fetch_complete_bug(bug_id)
    guessed_commits = {}

    def merge(y):
        for k in y.keys():
            if not guessed_commits.has_key(k):
                guessed_commits[k] = []
            guessed_commits[k].extend(y[k])

    if bug_data.has_key('comments'):
        merge(guess_from_comments(repo_dir, upstream, bug_data['comments']))
    if bug_data.has_key('attachments'):
        merge(guess_from_comments(repo_dir, upstream, bug_data['attachments']))
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
    # It's OK to not have any guesses, but it's seriously annoying when the
    # guessing logic kills the program!
    try:
        guesses = guess_commit(repo_dir, upstream, bug_id)
    except Exception, e:
        print >> sys.stderr, "WARNING: Unable to do guessing on %s" % bug_id
        print >> sys.stderr, e
        guesses = []

    def _list_commits():
        if len(commits) > 0:
            print "Commits entered:"
            for i in range(0, len(commits)):
                print "  %d) %s" % (i, commits[i])
        else:
            print "No commits entered"

    def _show_guesses():
        keys = guesses.keys()
        print "Guesses for bug %s" % bug_id
        print "-=-=" * 20
        for i in range(0, len(keys)):
            print "  %d) %s" % (i, keys[i])
            print "    BECAUSE:"
            for reason in guesses[keys[i]]:
                for line in reason.split('\n'):
                    print "          %s" % line

    def _open_browser():
        open_bug_in_browser(bug_id)

    prompt = "Bug %s %%d commits\nEnter one of a commit, 'guess', 'skip', 'browser', 'list', 'delete', 'delete-all' or 'done': " % bug_id
    print "=" * 80
    user_input = raw_input(prompt % len(commits)).strip()

    # This loop has gotten pretty disgusting.
    while user_input != 'done':
        if user_input == "list":
            _list_commits()
        elif user_input == "skip":
            uplift.skip_bug(bug_id)
            break
        elif user_input == "delete-all":
            commits = []
        elif user_input == "guess" and len(guesses) == 0:
            print "There are no guesses!"
        elif user_input == "guess" and len(guesses) > 0:
            g_prompt = "Enter the number of the commit to use, 'list', 'browser', 'all' for all or 'done' to end: "
            _show_guesses()
            g_input = raw_input(g_prompt).strip()
            while g_input != 'done':
                if g_input == 'all':
                    commits.extend(guesses.keys())
                elif g_input == 'list':
                    _list_commits()
                elif g_input == 'browser':
                    _open_browser()
                else:
                    try:
                        n = int(g_input, 10)
                        valid_input = True
                    except ValueError:
                        print "Invalid input: %s" % g_input
                        valid_input = False
                    if valid_input:
                        if n >= 0 and n < len(guesses.keys()):
                            # This is about as racey as Debbie does Dallas
                            commits.append(guesses.keys()[n])
                        else:
                            print "You entered an index that's out of the range 0-%d" % len(guesses.keys())
                if not g_input == 'list':
                    _show_guesses()
                g_input = raw_input(g_prompt).strip()
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
    r = copy.deepcopy(requirements)
    any_bug_has_commits = False
    for bug_id in r:
        if len(r[bug_id].get('commits', [])) > 0:
            any_bug_has_commits = True
            break
    if any_bug_has_commits and util.ask_yn("Some bugs already have commits.  Reuse them?"):
        return r
    for bug_id in requirements.keys():
        if len(r[bug_id].get('commits', [])) > 0:
            print "Found commits ['%s'] for bug %s" % ("', '".join(r[bug_id]['commits']), bug_id)
            if not util.ask_yn("Would you like to reuse these commits?"):
                r[bug_id]['commits'] = for_one_bug(repo_dir, bug_id, upstream)
        else:
            r[bug_id]['commits'] = for_one_bug(repo_dir, bug_id, upstream)

        # Save a temporary copy.  ugly!!!
        with open("requirements-tmp.json", "wb+") as f:
            json.dump(r, f, indent=2, sort_keys=True)
    return r


