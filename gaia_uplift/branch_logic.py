# https://wiki.mozilla.org/Release_Management/B2G_Landing
import bzapi
import os.path
import json

branch_rules_name = os.path.join(os.path.dirname(__file__), "branch_rules.json")

with open(branch_rules_name) as f:
    print "Using branch rules in %s" % branch_rules_name
    branch_rules = json.loads(f.read())

branches = branch_rules['branches']

status_flags = branch_rules['status_flags']

blocking_rules = branch_rules['blocking_rules']

patch_rules = branch_rules['patch_rules']

def flags_to_set(for_branches):
    fb = []
    for b in [x for x in for_branches if x in branches]:
        if b in status_flags.keys():
            fb.append(status_flags[b])
    return dict([(x, 'fixed') for x in fb])


def fixed_on_branches(bug):
    _branches = dict([(status_flags[k],k) for k in status_flags.keys()])
    b = []
    for x in ('fixed', 'verified'):
        for flag in _branches.keys():
            if bug.get(flag) == x and not _branches[flag] in b:
                b.append(_branches[flag])
    return b


def needed_on_branches(bug):
    needed_on = []
    fixed_on = fixed_on_branches(bug)

    def _a(x):
        for y in x:
            if not y in needed_on and not y in fixed_on and y in branches:
                needed_on.append(y)

    blocking_flag = bug.get('cf_blocking_b2g')
    if blocking_flag in blocking_rules.keys():
        _a(blocking_rules[blocking_flag])

    for flag in patch_rules.keys():
        for a in bug.get('attachments', []):
            for f in a.get('flags', []):
                if f['name'] == flag and f['status'] == '+':
                    _a(patch_rules[flag])

    return needed_on

