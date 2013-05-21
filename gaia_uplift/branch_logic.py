""" This module understands a which bugs related to which branches """
import bzapi

#branches = ['v1-train', 'v1.1.0', 'v1.0.1', 'v1.0.0']
branches = ['v1-train', 'v1.0.1']

def flags_to_set(branches):
    f = {}
    for b in branches:
        if b == 'v1-train' and b in branches:
            f['cf_status_b2g18'] = 'fixed'
        elif b == 'v1.0.0' and b in branches:
            f['cf_status_b2g18_1_0_0'] = 'fixed'
        elif b == 'v1.0.1' and b in branches:
            f['cf_status_b2g18_1_0_1'] = 'fixed'
        elif b == 'v1.1.0' and b in branches:
            f['cf_status_b2g18_1_1_0'] = 'fixed'
    return f


def fixed_on_branches(bug):
    b = []
    if bug.get('cf_status_b2g18') == 'fixed':
        b.append('v1-train')
    if bug.get('cf_status_b2g18_1_0_0') == 'fixed':
        b.append('v1.0.0')
    if bug.get('cf_status_b2g18_1_0_1') == 'fixed':
        b.append('v1.0.1')
    if bug.get('cf_status_b2g18_1_1_0') == 'fixed':
        b.append('v1.1.0')
    return b


def needed_on_branches(bug):
    needed_on = []
    fixed_on = fixed_on_branches(bug)

    def _a(x):
        if not x in needed_on and not x in fixed_on and x in branches:
            needed_on.append(x)

    blocking_b2g = bug['cf_blocking_b2g']

    if blocking_b2g == 'tef+' or blocking_b2g == 'shira+':
        _a('v1-train')
        _a('v1.0.1')
    elif blocking_b2g == 'leo+':
        _a('v1-train')
    else:
        for a in bug['attachments']:
            for f in a.get('flags', []):
                if f['name'] == 'approval-gaia-v1' and f['status'] == '+':
                    needed_on.append('v1-train')
    return needed_on

