# https://wiki.mozilla.org/Release_Management/B2G_Landing
import bzapi
import os.path
import json
import configuration as c

def flags_to_set(for_branches):
    """Take a list of branches and return a dictionary that contains
    pairings of flag name and flag value.  For the purposes of this
    program, we always use 'fixed'."""
    fb = []
    branches = c.read_value('repository.enabled_branches')
    status_flags = c.read_value('rules.status_flags')
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
    status_flags = c.read_value('rules.status_flags')
    branches = c.read_value('repository.enabled_branches')
    # I should figure out what this variable actually is and rename it!
    _branches = dict([(status_flags[k],k) for k in status_flags.keys()])
    b = []
    for x in ('fixed', 'verified'):
        for flag in _branches.keys():
            if bug.get(flag) == x and not _branches[flag] in b:
                if _branches[flag] in branches:
                    b.append(_branches[flag])
    return b


def needed_on_branches(bug):
    """Based on blocking flags and attachment flags, determine which
    branches the bug needs uplifting to"""
    needed_on = []
    fixed_on = fixed_on_branches(bug)

    branches = c.read_value('repository.enabled_branches')
    blocking_flag = bug.get(c.read_value('rules.blocking_flag'))
    blocking_rules = c.read_value('rules.blocking_rules')
    patch_rules = c.read_value('rules.patch_rules')

    def _a(x):
        for y in x:
            if not y in needed_on and not y in fixed_on and y in branches:
                needed_on.append(y)

    if blocking_flag in blocking_rules.keys():
        _a(blocking_rules[blocking_flag])

    for flag in patch_rules.keys():
        for a in bug.get('attachments', []):
            for f in a.get('flags', []):
                if f['name'] == flag and f['status'] == '+':
                    _a(patch_rules[flag])

    return needed_on

