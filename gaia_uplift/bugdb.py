try:
    import cPickle as pickle
except ImportError:
    import pickle

import time
import os

pickle_file = '.bugs.pcl'

def too_old(db):
    cur = time.gmtime()
    for i in range(0, 3):
        if cur[i] != db['created'][i]:
            return True
    return False

def db_create():
    return {
        'bugs': {},
        'created': time.gmtime()
    }

def init():
    global bug_db
    if os.path.exists(pickle_file):
        with open(pickle_file, 'r') as f:
            try:
                _bug_db = pickle.load(f)
            except:
                _bug_db = db_create()
            if too_old(_bug_db):
                os.unlink(pickle_file)
                bug_db = db_create()
            else:
                bug_db = _bug_db
    else:
        bug_db = db_create()

def store(bug):
    if not 'bug_db' in globals():
        init()

    bug_db['bugs'][int(bug['id'])] = bug
    with open(pickle_file, 'w+') as f:
        pickle.dump(bug_db, f)
        f.flush()

def load(bug_id):
    if not 'bug_db' in globals():
        init()
    if not bug_db['bugs'].has_key(int(bug_id)):
        return None
    return bug_db['bugs'][int(bug_id)]

def last_mod(bug_id):
    if not 'bug_db' in globals():
        return None
    if bug_db['bugs'].has_key(bug_id):
        return bug_db['bugs'][bug_id]['last_change_time']
    else:
        return None

