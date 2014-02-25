import unittest
import os
import json
import mock

import gaia_uplift.bzapi as bzapi
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

class FindBugsTest(unittest.TestCase):

    def test_find_bugs(self):
        with mock.patch('gaia_uplift.bzapi.search') as mock_search, \
             mock.patch('gaia_uplift.bzapi.parse_bugzilla_query') as mock_parse:

            mock_search.return_value = ['123456']
            mock_parse.return_value = ['my_butt']

            actual = subject.find_bugs(['snow_storm'])
            self.assertEqual(['123456'], actual)

            mock_parse.assert_called_once_with('snow_storm')
            mock_search.assert_called_once_with('my_butt')
            
    def test_find_bugs_only_skipable(self):
        with mock.patch('gaia_uplift.bzapi.search') as mock_search, \
             mock.patch('gaia_uplift.bzapi.parse_bugzilla_query') as mock_parse, \
             mock.patch('gaia_uplift.uplift.is_skipable') as mock_is_skipable:

            mock_search.return_value = ['123456']
            mock_parse.return_value = ['my_butt']
            mock_is_skipable.return_value = True

            actual = subject.find_bugs(['snow_storm'])
            self.assertEqual([], actual)

            mock_parse.assert_called_once_with('snow_storm')
            mock_is_skipable.assert_called_once_with('123456')
            mock_search.assert_called_once_with('my_butt')

