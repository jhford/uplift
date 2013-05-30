import bzapi

#branches = ['v1-train', 'v1.1hd', 'v1.0.1']
branches = ['v1-train', 'v1.0.1']

def flags_to_set(branches):
    f = {}
    for b in branches:
        if b == 'v1-train' and b in branches:
            f['cf_status_b2g18'] = 'fixed'
        # TODO: Need to verify if this is the correct flag!
        elif b == 'v1.1hd' and b in branches:
            f['cf_status_b2g18_1_1_hd'] = 'fixed'
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
    # TODO: Need to verify if this is the correct flag!
    if bug.get('cf_status_b2g18_1_1_hd') == 'fixed':
        b.append('v1.1hd')
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
        _a('v1.1hd')
        _a('v1.0.1')
    elif blocking_b2g == 'leo+':
        _a('v1-train')
        _a('v1.1hd')
    else:
        for a in bug['attachments']:
            for f in a.get('flags', []):
                if f['name'] == 'approval-gaia-v1' and f['status'] == '+':
                    _a('v1-train')
                    _a('v1.1hd')
    return needed_on

