import time
import os
import json

def e_join(l, t="and", s=", "):
    """Join a list of strings in an intelligble way for display
    a, b, c becomes a, b and c with default params"""
    if len(l) == 0:
        return ""
    elif len(l) == 1:
        return l[0]
    else:
        return s.join(l[:-1]) + " %s " % t + str(l[-1])

def time_start():
    return time.time()

def time_end(start_time):
    return time.time() - start_time

def time_str(t=None):
    return time.strftime("%Y_%m_%d_%H%M%S", t if t else time.localtime())

def ask_yn(q, default=True):
    """Give me a question, I'll ask it and give you the result.
    Default of True means that we'll accept '\n' as Yes.
    Default of False means that we'll accept '\n' as No.
    We'll accept y, yes, n or no"""
    if default is True:
        default_string = " [Y/n]: "
    elif default is False:
        default_string = " [y/N]: "
    else:
        raise Exception("invalid default value")
    prompt = q + default_string
    u = raw_input(prompt).lower()
    while not (u == 'y' or u == 'yes' or u == 'n' or u == 'no' or u == ''):
        u = raw_input(prompt).lower()
    if u == 'y' or u == 'yes' or (default and u == ''):
        return True
    elif u == 'n' or u == 'no' or (not default and u == ''):
        return False
    else:
        raise Exception("This question asker is busted")


def read_json(path):
    if os.path.exists(path):
        with open(path, 'rb') as f:
            return json.load(f)
    return None


def write_json(path, data):
    with open(path, 'wb+') as f:
        json.dump(data, f, indent=2, sort_keys=True)

