# https://wiki.mozilla.org/Release_Management/B2G_Landing
import bzapi
import os.path
import json

branch_rules_name = os.path.join(os.path.dirname(__file__), "branch_rules.json")

with open(branch_rules_name) as f:
    print "Using branch rules in %s" % branch_rules_name
    branch_rules = json.loads(f.read())

# This is a list of branches which we'll operate on.  This makes
# it possible to keep rules for older branches around but only
# consider new branches
branches = branch_rules['branches']

# This is a dictionary which maps branches to status flags
# e.g. when you land on v1.3, you set status-b2g-v1.3 to 'fixed'
status_flags = branch_rules['status_flags']

# Some bugs are blocking the release, this tells us which flag
# is the one that tells us who's blocking
blocking_flag = branch_rules['blocking_flag']

# Based on which blocking flag we have, we need to know which
# branches need the patch
blocking_rules = branch_rules['blocking_rules']

# Some patches are approved to land on a branch but don't block
# a release.  This is a dictionary of attachment flags to branch
# mappings.
patch_rules = branch_rules['patch_rules']

def flags_to_set(for_branches):
    """Take a list of branches and return a dictionary that contains
    pairings of flag name and flag value.  For the purposes of this
    program, we always use 'fixed'."""
    fb = []
    for b in [x for x in for_branches if x in branches]:
        if b in status_flags.keys():
            fb.append(status_flags[b])
    return dict([(x, 'fixed') for x in fb])


def fixed_on_branches(bug):
    """Take a bug dictionary and use the bugzilla flags to determine
    which branches the bug is fixed or verifed on.  This does not
    look at the contents of the repository because that's impossible
    to do correctly.  If you git revert a commit, the original commit
    is still 'on' the branch, but substantively absent"""
    _branches = dict([(status_flags[k],k) for k in status_flags.keys()])
    b = []
    for x in ('fixed', 'verified'):
        for flag in _branches.keys():
            if bug.get(flag) == x and not _branches[flag] in b:
                b.append(_branches[flag])
    return b


def needed_on_branches(bug):
    """Based on blocking flags and attachment flags, determine which
    branches the bug needs uplifting to"""
    needed_on = []
    fixed_on = fixed_on_branches(bug)

    def _a(x):
        for y in x:
            if not y in needed_on and not y in fixed_on and y in branches:
                needed_on.append(y)

    _blocking_flag = bug.get(blocking_flag)
    if _blocking_flag in blocking_rules.keys():
        _a(blocking_rules[_blocking_flag])

    for flag in patch_rules.keys():
        for a in bug.get('attachments', []):
            for f in a.get('flags', []):
                if f['name'] == flag and f['status'] == '+':
                    _a(patch_rules[flag])

    return needed_on

