# https://wiki.mozilla.org/Release_Management/B2G_Landing
import bzapi

branches = ['v1.3', 'v1.2']

status_flags = {
    'v1.3': 'cf_status_b2g_1_3',
    'v1.2': 'cf_status_b2g_1_2',
    'v1-train': 'cf_status_b2g18',
    'v1.0.1': 'cf_status_b2g18_1_0_1',
    'v1.0.0': 'cf_status_b2g18_1_0_0',
    'v1.1.0hd': 'cf_status_b2g_1_1_hd'
}

blocking_rules = {
    '1.3+': ['v1.3'],
    'koi+': ['v1.3', 'v1.2'],
    'leo+': ['v1.3', 'v1.2', 'v1-train'],
    'tef+': ['v1.3', 'v1.2', 'v1-train', 'v1.0.1'],
    'shira+': ['v1.3', 'v1.2', 'v1-train', 'v1.0.1'],
}

patch_rules = {
    'approval-gaia-v1': ['v1.3', 'v1.2', 'v1-train'],
    'approval-gaia-v1.2': ['v1.3', 'v1.2'],
}

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

