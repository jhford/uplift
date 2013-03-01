import sys
import copy

import git
import util

def open_bug_in_browser(bug_id):
    """I know how to open a bug for inspection"""
    if sys.platform == "darwin":
        git.run_cmd(["open", "https://bugzilla.mozilla.org/show_bug.cgi?id=%d" % int(bug_id)], workdir='.')
    elif sys.platform == "linux2":
        git.run_cmd(["firefox", "https://bugzilla.mozilla.org/show_bug.cgi?id=%d" % int(bug_id)], workdir='.')


def for_one_bug(repo_dir, bug_id):
    """ Given a bug id, let's find the commits that we care about.  Right now, make the hoo-man dooo eeeet"""
    open_bug_in_browser(bug_id)
    # TODO:  This function should be smarter.  It should scan the bug comments and attachements and 
    #        see if it can find sha1 sums which point to the master branch commit information.  
    #        This function should also take a 'from_branch' parameter to figure out which branch
    #        the changes are coming from
    commits=[]
    prompt = "Type in a commit that is needed for %s or 'done' to end: " % bug_id
    user_input = raw_input(prompt).strip()
    while user_input != 'done':
        if git.valid_id(user_input):
            try:
                full_rev = git.get_rev(repo_dir, id=user_input)
                print "appending %s to the list of revisions to use" % full_rev
                commits.append(full_rev)
            except sp.CalledProcessError, e:
                print "This sha1 commit id (%s) is valid but not found in %s" % (user_input, repo_dir)
        else:
            print "This is not a sha1 commit id: %s" % user_input
        user_input = raw_input(prompt).strip()
    return commits


def for_all_bugs(repo_dir, requirements):
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
                r[bug_id]['commits'] = for_one_bug(repo_dir, bug_id)
        else:
            r[bug_id]['commits'] = for_one_bug(repo_dir, bug_id)
    return r


