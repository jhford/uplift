import json
import prettytable as pt

import branch_logic
import util
import git


def trim_words(s, max=90):
    if len(s) <= max:
        return s
    else:
        i = max - 3
        while s[i] != ' ':
            i -= 1
        return s[:i] + '...'


def display_uplift_requirements(requirements, max_summary=90):
    """Generate a PrettyTable that shows the bug id, branch status
    and first up to 100 chars of the summary"""
    headers = ['Bug'] + ['%s status' % x for x in branch_logic.branches] + ['Summary']
    t = pt.PrettyTable(headers)
    t.align['Bug'] = "l"
    t.align['Summary'] = "l"
    for bug_id in requirements.keys():
        bug = requirements[bug_id]
        row = [bug_id]
        needed_on = bug['needed_on']
        fixed_on = bug['already_fixed_on']
        for branch in branch_logic.branches:
            if branch in fixed_on:
                row.append("fixed")
            elif branch in needed_on:
                row.append("needed")
            else:
                row.append("---")

        t.add_row(row + [trim_words(bug['summary'])])
    return t


def display_uplift_report(report, max_summary=90):
    """Generate a PrettyTable that shows the bug id, branch status
    and first up to 100 chars of the summary"""
    headers = ['Bug'] + ['%s commit' % x for x in ['master'] + branch_logic.branches] + ['Summary']
    t = pt.PrettyTable(headers)
    t.align['Bug'] = "l"
    t.align['Summary'] = "l"
    for bug_id in report.keys():
        bug = report[bug_id]
        row = [bug_id]
        master_commits = bug['commits']
        row.append("\n".join([x[:7] for x in master_commits]) if len(master_commits) > 0 else "skipped")
        for branch in branch_logic.branches:
            branch_commits = []
            for mcommit in master_commits:
                if bug.has_key('uplift_status'):
                    if branch in bug['uplift_status'][mcommit]['success'].keys():
                        branch_commits.append(bug['uplift_status'][mcommit]['success'][branch])
                    elif branch in bug['uplift_status'][mcommit]['failure']:
                        branch_commits.append("failed")
                    else:
                        branch_commits.append("---")
            if len(branch_commits) == 0:
                row.append("---")
            else:
                row.append("\n".join([x[:7] for x in branch_commits]))


        t.add_row(row + [trim_words(bug['summary'])])
    return t


def merge_script(repo_dir, commit, branches):
    full_commit = git.get_rev(repo_dir, commit)
    s=["  git checkout %s" % branches[0]]
    master_num = git.determine_cherry_pick_master_number(repo_dir, commit, 'master')
    if not master_num:
        master_num = ""
    s.append("  git cherry-pick -x %s %s" % (master_num, full_commit))
    s.append("  <RESOLVE MERGE CONFLICTS>")
    s.append("  git commit")
    for branch in branches[1:]:
        s.append("  git checkout %s" % branch)
        s.append("  git cherry-pick -x $(git log -n1 %s)" % branches[0])
    return "\n".join(s)


def display_good_bug_comment(repo_dir, bug_id, bug):
    """Print everything that's needed for a good bug"""
    r=["="*80,
       "COMMENT FOR BUG https://bugzilla.mozilla.org/show_bug.cgi?id=%s" % bug_id,
       "",
       "Set these flags:"]
    for flag in bug['flags_to_set'].keys():
        r.append("  * %s -> %s" % (flag, bug['flags_to_set'][flag]))
    r.extend(["", "Make this comment:"])
    for commit in bug['commits']:
        r.append("Uplifted commit %s as:" % commit)
        for branch in bug['uplift_status'][commit]['success'].keys():
            r.append("%s: %s" % (branch, bug['uplift_status'][commit]['success'][branch]))
    r.extend(["", "-"*80])
    return "\n".join(r)


def display_bad_bug_comment(repo_dir, bug_id, bug):
    """Print everything that's needed for a bad bug"""
    r = ["="*80,
         "COMMENT FOR BUG %s" % bug_id,
         "https://bugzilla.mozilla.org/show_bug.cgi?id=%s" % bug_id,
         "",
         "I was not able to uplift this bug to %s.  If this bug has dependencies " % util.e_join(bug['needed_on']) +
         "which are not marked in this bug, please comment on this bug.  " +
         "If this bug depends on patches that aren't approved for %s, " % util.e_join(bug['needed_on']) +
         "we need to re-evaluate the approval.  " +
         "Otherwise, if this is just a merge conflict, you might be able to resolve " +
         "it with:",
         ""]
    for commit in git.sort_commits(repo_dir, bug['commits'], 'master'):
        r.append(merge_script(repo_dir, commit, bug['uplift_status'][commit]['failure']))
    r.extend(["", "-"*80])
    return "\n".join(r)


def display_ugly_bug_comment(repo_dir, bug_id, bug):
    """Print everything that's needed for an ugly bug"""
    r = ["="*80,
         "BUG https://bugzilla.mozilla.org/show_bug.cgi?id=%s IS MESSED UP!" % bug_id,
         "",
         json.dumps(indent=2, sort_keys=True),
         "-"*80,""]
    return "\n".join(r)


def classify_gbu(report):
    """I figure out which bugs are good, bad and ugly.  Good means that everything
    that was desired happened.  Bad means that nothing happened.  Ugly means that
    there was partial success"""
    good = []
    bad = []
    ugly = []
    for bug_id in [x for x in report.keys() if report[x].has_key('uplift_status')]:
        n_success = n_failure = 0
        bug = report[bug_id]
        for commit in bug['uplift_status'].keys():
            n_success += len(bug['uplift_status'][commit]['success'].keys())
            n_failure += len(bug['uplift_status'][commit]['failure'])
        if n_success > 0 and n_failure > 0:
            ugly.append(bug_id)
        elif n_success > 0 and n_failure == 0:
            good.append(bug_id)
        elif n_failure > 0 and n_success == 0:
            bad.append(bug_id)
        else:
            raise Exception("What the hell is going on here!")
    return good, bad, ugly


def display_uplift_comments(repo_dir, report):
    skipped_bugs = [x for x in report.keys() if not report[x].has_key('uplift_status')]
    good = [] # All commits on all branches
    bad = [] # No commits
    ugly = [] # Partial uplift
    good, bad, ugly = classify_gbu(report)
    r = ["Skipped bugs: %s" % ", ".join(skipped_bugs),
         "Good Bugs: %s" % ", ".join(good),
         "Bad Bugs: %s" % ", ".join(bad),
         "Ugly Bugs: %s" % ", ".join(ugly)]
    for bug_id in good:
        r.append(display_good_bug_comment(repo_dir, bug_id, report[bug_id]))
    for bug_id in bad:
        r.append(display_bad_bug_comment(repo_dir, bug_id, report[bug_id]))
    for bug_id in ugly:
        r.append(display_ugly_bug_comment(repo_dir, bug_id, report[bug_id]))
    return "\n".join(r)


