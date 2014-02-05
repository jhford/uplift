import unittest
import os
import gaia_uplift.bugdb as subject
import time

local_pickle_file = 'test.pickle'
if os.path.exists(local_pickle_file):
    os.unlink(local_pickle_file)
subject.pickle_file = local_pickle_file

old_time = time.struct_time((1900, 0, 0, 0, 0, 0, 0, 0, 0))

class BugDbTest(unittest.TestCase):
    def setUp(self):
        if os.path.exists(local_pickle_file):
            os.unlink(local_pickle_file)
        if 'bug_db' in dir(subject):
            del subject.bug_db


class DBCreate(unittest.TestCase):
    def test_create(self):
        result = subject.db_create()
        self.assertEqual({}, result['bugs'])
        self.assertEqual(time.struct_time, type(result['created']))
        self.assertEqual(['bugs', 'created'], result.keys())

class TooOld(unittest.TestCase):
    def test_is_too_old(self):
        test_db = {
            'created': old_time
        }
        self.assertTrue(subject.too_old(test_db))

    def test_is_not_too_old(self):
        # NOTE: Technically, this test could fail if the test is run
        # at the moment that the day changes in Zulu
        test_db = subject.db_create()
        self.assertFalse(subject.too_old(test_db))

class Init(BugDbTest):

    def test_one_init(self):
        subject.init()
        self.assertTrue('bug_db' in dir(subject))

    def test_invalid_pickle(self):
        with open(local_pickle_file, 'w+') as f:
            f.write("THIS AIN'T NO STINKIN' PICKLE")
        subject.init()

    def test_too_old_db(self):
        subject.init()
        subject.bug_db['bugs'][123] = 'JUNK'
        subject.bug_db['created'] = old_time
        subject.init()
        self.assertFalse(os.path.exists(local_pickle_file))
        self.assertEqual({}, subject.bug_db['bugs'])
        self.assertNotEqual(old_time, subject.bug_db['created'])

class Store(BugDbTest):
    def test_store_no_existing_db(self):
        self.assertFalse(os.path.exists(local_pickle_file))
        subject.store({'id': 1234, 'data': 'john'})
        self.assertEqual(subject.bug_db['bugs'][1234]['data'], 'john')
        self.assertTrue(os.path.exists(local_pickle_file))

    def test_store_existing_db(self):
        subject.init()
        subject.store({'id': 1233, 'data': 'otherjohn'})
        self.assertTrue(os.path.exists(local_pickle_file))
        subject.store({'id': 1234, 'data': 'john'})
        self.assertEqual(subject.bug_db['bugs'][1234]['data'], 'john')
        self.assertTrue(os.path.exists(local_pickle_file))

    def test_store_str_id_parsable(self):
        subject.store({'id': '1234'})
        self.assertEqual({'id': '1234'}, subject.bug_db['bugs'][1234])

    def test_store_str_id_non_parsable(self):
        with self.assertRaises(ValueError):
            subject.store({'id': 'bannana'})

class Load(BugDbTest):
    def setUp(self):
        subject.store({
            'id': 1234,
            'data': 'john'
        })

    def test_load_extant(self):
        bug = subject.load(1234)
        self.assertEqual('john', bug['data'])

    def test_load_non_extant(self):
        bug = subject.load(1111)
        self.assertTrue(bug is None)

class LastMod(BugDbTest):
    def test_bug_is_there(self):
        test_bug = {
            'id': 1234,
            'last_change_time': 'john'
        }
        subject.store(test_bug)
        self.assertEqual('john', subject.last_mod(1234))

    def test_bug_is_absent(self):
        self.assertTrue(subject.last_mod(1111) is None)

    def test_bug_absent_db_exists(self):
        subject.store({'id': 1235})
        self.assertTrue(subject.last_mod(1111) is None)

