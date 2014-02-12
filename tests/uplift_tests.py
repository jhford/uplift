import unittest
import os
import json

import gaia_uplift.uplift as subject

class BugSkipping(unittest.TestCase):

    def setUp(self):
        subject.skip_bugs_file = 'test.skip_bugs'
        if os.path.exists(subject.skip_bugs_file):
            os.unlink(subject.skip_bugs_file)

    def test_add_int_bug_to_skip(self):
        bugid = 12345
        subject.skip_bug(bugid)
        with open(subject.skip_bugs_file) as f:
            self.assertEqual([bugid], json.load(f))

    def test_add_str_bug_to_skip(self):
        bugid = 12345
        subject.skip_bug(str(bugid))
        with open(subject.skip_bugs_file) as f:
            self.assertEqual([bugid], json.load(f))

    def test_add_bug_twice(self):
        bugid = 12345
        subject.skip_bug(bugid)
        subject.skip_bug(bugid)
        with open(subject.skip_bugs_file) as f:
            self.assertEqual([bugid], json.load(f))

    def test_is_skippable_not_skipable(self):
        bugid = 12345
        self.assertFalse(subject.is_skipable(bugid))

    def test_is_skippable_skipable(self):
        bugid = 12345
        subject.skip_bug(12345)
        self.assertTrue(subject.is_skipable(bugid))

