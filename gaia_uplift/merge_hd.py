
import sys
import os
import re

import git
import util
import branch_logic
import bzapi

def merge(repo_dir, gaia_url, branch_to, branch_from):
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

    print "Merging %s into branch %s" % (branch_from, branch_to)
    if not branch_to in git.branches(repo_dir):
        print >> sys.stderr, "Asking to merge into a branch that doesn't exist (%s)" % branch_to
        return None
    if not branch_from in git.branches(repo_dir):
        print >> sys.stderr, "Asking to merge from a branch that doesn't exist (%s)" % branch_from
        return None
    
    git.checkout(repo_dir, branch_to)
    start_commit = git.get_rev(repo_dir)
    git.merge(repo_dir, branch_from, strategy='recursive')
    end_commit = git.get_rev(repo_dir)
    print "Merge range is %s..%s" % (start_commit[:7], end_commit[:7])
    print git.log(repo_dir, "%s..%s" % (start_commit, end_commit), pretty="oneline")
    print "Dry Run push"
    git.push(repo_dir, remote="origin", branches=[branch_to], dry_run=True)
    info = git.push(repo_dir, remote="origin", branches=[branch_to])
    print "Would be pusing to %s" % info['url']
    for branch in info['branches'].keys():
        s,e = info['branches'][branch]
        print "  %s: %s..%s" % (branch,s,e)
    if util.ask_yn("Push for realises?"):
        info = git.push(repo_dir, remote="origin", branches=[branch_to], dry_run=False)
        print "Pushed to %s" % info['url']
        for branch in info['branches'].keys():
            s,e = info['branches'][branch]
            print "  %s: %s..%s" % (branch,s,e) 
        comment(repo_dir, branch_to, "%s..%s" % (start_commit, end_commit))


valid_bug_id = '(?P<bug>\d{6})'

bug_id_patterns = [re.compile(x, re.I|re.M) for x in [
    'bug {,3}%s' % valid_bug_id, # This is most bugs
    'bug[_:\- ]{,3}%s' % valid_bug_id, # This is most bugs
    '\w+/%s' % valid_bug_id, # This is the case where the bug is like jhford/123456
]]


def guess_bug_id(repo_dir, commit):

    def _show_bugs():
        print "Possible bugs:"
        for i in range(0, len(possible_bug_ids)):
            print "%d) Bug %s: %s" % (i, possible_bug_ids[i], bug_summaries.get(possible_bug_ids[i], "Closed bug"))


    msg = git.log(repo_dir, commit, number=1, pretty="%B")
    bug_ids = []
    possible_bug_ids = []
    bug_summaries = {}
    for pattern in bug_id_patterns:
        possible_bug_ids.extend([int(x) for x in pattern.findall(msg)])
    possible_bug_ids = list(set(sorted(possible_bug_ids)))
    for bug in possible_bug_ids:
        bug_data = bzapi.fetch_bug(bug, include_fields="summary")
        if bug_data.has_key('summary'):
            bug_summaries[bug] = bug_data['summary']

    print "Commit %s has a body of:\n%s" % (commit, msg.strip())
    print "-" * 80

    if len(possible_bug_ids) == 1:
        print "I only found one bug:\nBug %s -- %s" % (possible_bug_ids[0], bug_summaries.get(possible_bug_ids[0], "Closed bug"))
        if util.ask_yn("Use it?"):
            bug_ids = possible_bug_ids
    elif len(possible_bug_ids) > 0:
        _show_bugs()
        index = None
        prompt = "index, 'clear' or 'done' %s: "
        _input = raw_input(prompt % str(bug_ids))
        while _input.strip().lower() != 'done':
            if _input.strip().lower() == 'clear':
                bug_ids = []
            else:
                try:
                    i = int(_input.strip())
                    if possible_bug_ids[i] in bug_ids:
                        print "Dude, this is already there!"
                    else:
                        bug_ids.append(possible_bug_ids[i])
                except:
                    print "try again!"
                    pass
            _input = raw_input(prompt % str(bug_ids))
    else:
        print "There are no bugs to guess from"
    print "=" * 80
    return bug_ids


def comment(repo_dir, branch_to, commit_range, dry_run=False):
    all_commits = git.log(repo_dir, commit_range, pretty="%H").strip().split('\n')
    comments = {}
    commits_without_bugs = []

    assert branch_to in git.branches(repo_dir), "branch parameter must be a branch"

    i = 0
    for commit in all_commits:
        i += 1
        print "bug %d of %d" % (i, len(all_commits))
        bug_ids = guess_bug_id(repo_dir, commit)
        if bug_ids is None or len(bug_ids) == 0:
            commits_without_bugs.append(commit)
        else:
            for bug_id in bug_ids:
                if not bug_id in comments.keys():
                    comments[bug_id] = []
                comments[bug_id].append(commit)

    failed_bugs = []

    for bug_id in comments.keys():
        comment = []
        flags = branch_logic.flags_to_set([branch_to])
        for commit in comments[bug_id]:
            comment.append("v1.1.0hd: %s" % commit)
        comment = '\n'.join(comment)
        print "Commenting on bug %s with:\ntext: %s\nflags: %s" % (bug_id, comment, flags)
        if not dry_run:
            try:
                bzapi.update_bug(bug_id, comment=comment, values=flags)
            except:
                failed_bugs.append(bug_id)
    print "The following commits do not have a bug associated with them:\n%s" % commits_without_bugs
    print "Failed to comment on the following bugs:\n%s" % failed_bugs
