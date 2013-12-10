# https://wiki.mozilla.org/Release_Management/B2G_Landing
import bzapi

branches = ['v1.2', 'v1-train', 'v1.1.0hd'] #, 'v1.0.1']

def flags_to_set(for_branches):
    fb = []
    for b in [x for x in for_branches if x in branches]:
        if b == 'v1.3':
            fb.append('cf_status_b2g_1_3')
        elif b == 'v1.2':
            fb.append('cf_status_b2g_1_2')
        elif b == 'v1-train':
            fb.append('cf_status_b2g18')
        elif b == 'v1.0.0':
            fb.append('cf_status_b2g18_1_0_0')
        elif b == 'v1.0.1':
            fb.append('cf_status_b2g18_1_0_1')
        elif b == 'v1.1.0':
            fb.append('cf_status_b2g18_1_1_0')
        elif b == 'v1.1.0hd':
            fb.append('cf_status_b2g_1_1_hd')
    return dict([(x, 'fixed') for x in fb])


def fixed_on_branches(bug):
    b = []
    for x in ('fixed', 'verified'):
        if bug.get('cf_status_b2g_1_3') == x:
            b.append('v1.3')
        if bug.get('cf_status_b2g_1_2') == x:
            b.append('v1.2')
        if bug.get('cf_status_b2g18') == x:
            b.append('v1-train')
        if bug.get('cf_status_b2g18_1_0_0') == x:
            b.append('v1.0.0')
        if bug.get('cf_status_b2g18_1_0_1') == x:
            b.append('v1.0.1')
        if bug.get('cf_status_b2g18_1_1_0') == x:
            b.append('v1.1.0')
        if bug.get('cf_status_b2g_1_1_hd') == x:
            b.append('v1.1.0hd')
    return b


def needed_on_branches(bug):
    needed_on = []
    fixed_on = fixed_on_branches(bug)

    def _a(x):
        if not x in needed_on and not x in fixed_on and x in branches:
            needed_on.append(x)

    blocking_b2g = bug['cf_blocking_b2g']

    if blocking_b2g == 'v1.3+':
        _a('v1.3')
    elif blocking_b2g == 'koi+':
        _a('v1.3')
        _a('v1.2')
    elif blocking_b2g == 'leo+':
        _a('v1.3')
        _a('v1.2')
        _a('v1-train')
    elif blocking_b2g == 'tef+' or blocking_b2g == 'shira+':
        _a('v1.3')
        _a('v1.2')
        _a('v1-train')
        _a('v1.0.1')
    else:
        for a in bug['attachments']:
            for f in a.get('flags', []):
                if f['name'] == 'approval-gaia-v1' and f['status'] == '+':
                    _a('v1.3')
                    _a('v1.2')
                    _a('v1-train')
                elif f['name'] == 'approval-gaia-v1.2' and f['status'] == '+':
                    _a('v1.3')
                    _a('v1.2')
    return needed_on

