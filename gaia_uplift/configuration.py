import os
import json

STRING='string'
INT='int'


def init(alt_json=None):
    global config
    global config_file
    if alt_json:
        config_file = alt_json
    else:
        config_file = os.path.join(os.path.dirname(os.getcwd()), 'config.json')
    if os.path.exists(json_file):
        with open(json_file) as f:
            config = json.load(f)
    else:
        config = {}


def lookup(key, obj):
    """Take a key like john.ford.test and return obj[john][ford][test]
    if that's a valid thing to do"""
    keys = key.split('.')
    x=obj
    for y in range(0, len(keys)):
        if not issubclass(type(x), dict):
            raise KeyError('key does not point to a dict')
        if x.has_key(keys[y]):
            x=x[keys[y]]
        else:
            raise KeyError(
                '%s is not in the configuration object. First absent key is %s'
                % (key, keys[y]))
    return x


def present(key, obj):
    # Much lazy
    try:
        lookup(key, obj)
        return True
    except KeyError:
        return False


def store(key, value, obj):
    keys = key.split('.')
    x=obj
    for y in range(0, len(keys) - 1):
        if not issubclass(type(x), dict):
            raise KeyError('Will not overwrite non-dict key with dict')
        if not x.has_key(keys[y]):
            x[keys[y]] = {}
        x=x[keys[y]]
    x[keys[-1]] = value


# For unit testing this
_raw_input = raw_input


def ask_for_value(name, t=STRING):
    if not (t is STRING or t is INT):
        raise TypeError('type is not valid')
    prompt = 'Input value for %s (type %s): ' % (name, t) 
    user_input = _raw_input(prompt).strip()
    valid_input = None
    while not valid_input:
        if t is STRING:
            return user_input
        elif t is INT:
            try:
                return int(user_input)
            except:
                pass
        user_input = _raw_input(prompt).strip()
    return valid_input


def read_value(key, ask_if_missing=False):
    if not 'config' in globals():
        init()

    if ask_if_missing:
        if present(key, config):
            return lookup(key, config)
        else:
            new_value = ask_for_value(key, t=STRING)
            store(key, new_value, config)
            return lookup(key, config)
    else:
        return lookup(key, config)

