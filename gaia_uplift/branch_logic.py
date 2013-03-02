""" This module understands a which bugs related to which branches """

#TODO: This module should be more declaritive and data driven than it is

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
    if bug['cf_status_b2g18'] == 'fixed':
        b.append('v1-train')
    if bug['cf_status_b2g18_1_0_0'] == 'fixed':
        b.append('v1.0.0')
    if bug['cf_status_b2g18_1_0_1'] == 'fixed':
        b.append('v1.0.1')
    #if bug['cf_status_b2g18_1_1_0'] == 'fixed':
    #    b.append('v1.1.0')
    return b


def needed_on_branches(bug):
    blocking_b2g = bug['cf_blocking_b2g']

    if blocking_b2g == 'tef+' or blocking_b2g == 'shira+':
        #branches.extend(['v1-train', 'v1.1.0', 'v1.0.1'])
        return ['v1-train', 'v1.0.1']
    elif blocking_b2g == 'leo+':
        return ['v1-train', 'v1.1.0']
    else:
        for a in bug['attachments']:
            for f in a.get('flags', []):
                if f['name'] == 'approval-gaia-v1' and f['status'] == '+':
                    return ['v1-train']
    return []

def determine_branches(bug_id):
    bug = bzapi.fetch_bug(bug_id)
    branches = []

    fixed_on = fixed_on_branches(bug)
    for branch in needed_on_branches(bug):
        if not branch in fixed_on:
            branches.append(branch)

    print "Bug %s -- %s\nneeds to be uplifted to '%s'" % (bug_id, bug['summary'], "', '".join(branches))
    return {
        'branches': branches,
        'summary': bug['summary'],
    }

