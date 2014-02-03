def make_bug(overrides={}):
    bug = {}
    bug.update(overrides)
    return bug

def make_user(overrides={}):
    user = {
        'name': 'user@bugzilla.com',
        'real_name': 'Bugzilla User',
        'ref': 'invalid-ref'
    }
    user.update(overrides)
    return user

def make_attachment_flag(overrides={}):
    flag = {
        'id': 1234567,
        'name': 'example-flag',
        'setter': make_user(),
        'status': '?',
        'type_id': 4
    }
    flag.update(overrides)
    return flag

def make_attachment(overrides={}):
    attachment = {
        'description': 'a c file',
        'file_name': 'test.c'
    }
    attachment.update(overrides)
    return attachment 
