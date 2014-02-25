import unittest
import os
import json
from mock import patch

import gaia_uplift.git as git
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
        with patch('gaia_uplift.bzapi.search') as search, \
             patch('gaia_uplift.bzapi.parse_bugzilla_query') as parse:

            search.return_value = ['123456']
            parse.return_value = ['my_butt']

            actual = subject.find_bugs(['snow_storm'])
            self.assertEqual(['123456'], actual)

            parse.assert_called_once_with('snow_storm')
            search.assert_called_once_with('my_butt')
            
    def test_find_bugs_only_skipable(self):
        with patch('gaia_uplift.bzapi.search') as search, \
             patch('gaia_uplift.bzapi.parse_bugzilla_query') as parse, \
             patch('gaia_uplift.uplift.is_skipable') as is_skipable:

            search.return_value = ['123456']
            parse.return_value = ['my_butt']
            is_skipable.return_value = True

            actual = subject.find_bugs(['snow_storm'])
            self.assertEqual([], actual)

            parse.assert_called_once_with('snow_storm')
            is_skipable.assert_called_once_with('123456')
            search.assert_called_once_with('my_butt')

class OrderCommits(unittest.TestCase):
    def test_order_commits(self):
        with patch('gaia_uplift.git.sort_commits') as sort:
            expected = range(5)
            requirements = dict([(x, {'commits': [x]}) for x in expected])
            sort.return_value = expected
            actual = subject.order_commits(None, requirements)
            self.assertEqual(expected, actual)
            sort.assert_called_once_with(None, expected, 'master')

    def test_order_commits_no_commits(self):
        with patch('gaia_uplift.git.sort_commits') as sort:
            iterations = range(5)
            expected = [x for x in iterations if x % 2 == 0]
            requirements = dict([(x, {'commits': [x]}) if x % 2 == 0 else (x, {}) for x in iterations])
            sort.return_value = expected
            actual = subject.order_commits(None, requirements)
            self.assertEqual(expected, actual)
            sort.assert_called_once_with(None, expected, 'master')

class UpliftCommit(unittest.TestCase):
    def test_success_two_branches(self):
        with patch('gaia_uplift.git.cherry_pick') as cherry_pick:
            branches = ['v1', 'v2']

            cherry_pick.side_effect = ["%ssha" % x for x in branches]

            actual = subject.uplift_commit(None, 'commit', branches)
            expected = {
                'success': {'v1': 'v1sha', 'v2': 'v2sha'},
                'failure': []
            }
            self.assertEqual(expected, actual)

    def test_one_fail_one_pass(self):
        with patch('gaia_uplift.git.cherry_pick') as cherry_pick:
            branches = ['v1', 'v2']

            cherry_pick.side_effect = ['v1sha', git.GitError]

            actual = subject.uplift_commit(None, 'commit', branches)
            expected = {
                'success': {'v1': 'v1sha'},
                'failure': ['v2']
            }
            self.assertEqual(expected, actual)

    def test_failure_two_branches(self):
        with patch('gaia_uplift.git.cherry_pick') as cherry_pick:
            branches = ['v1', 'v2']

            cherry_pick.side_effect = [git.GitError, git.GitError]

            actual = subject.uplift_commit(None, 'commit', branches)
            expected = {
                'success': {},
                'failure': ['v1', 'v2']
            }
            self.assertEqual(expected, actual)

    def test_noop(self):
        with patch('gaia_uplift.git.cherry_pick') as cherry_pick:
            commit = 'abc123'
            cherry_pick.return_value = commit
            actual = subject.uplift_commit(None, commit, ['v1'])
            expected = {
                'success': {'v1': commit},
                'failure': []
            }
            self.assertEqual(expected, actual)

class Push(unittest.TestCase):
    def test_success(self):
        with patch('gaia_uplift.git.push') as push, \
             patch('gaia_uplift.util.ask_yn') as ask_yn:
            ask_yn.return_value = True
            expected = {'url': None,
                        'branches': { 'master': ("a"*40, "b"*40) }
                       }
            
            push.return_value = expected
            actual = subject.push(None)
            self.assertEqual(expected, actual)

    def test_no_push(self):
        with patch('gaia_uplift.git.push') as push, \
             patch('gaia_uplift.util.ask_yn') as ask_yn:

            preview = {'url': None,
                        'branches': { 'master': ("a"*40, "b"*40) }
            }
            push.return_value = preview
            ask_yn.return_value = False
            self.assertEqual(None, subject.push(None))

    def test_abject_failure(self):
        with patch('gaia_uplift.git.push') as push, \
             patch('gaia_uplift.util.ask_yn') as ask_yn:

            preview = {'url': None,
                       'branches': {'master': ("a"*40, "b"*40) }
            }
            ask_yn.return_value = False
            push.side_effect = git.PushFailure
            with self.assertRaises(git.PushFailure):
                subject.push(None)

    def test_recovery(self):
        with patch('gaia_uplift.git.push') as push, \
             patch('gaia_uplift.util.ask_yn') as ask_yn:
            ask_yn.return_value = True
            expected = {'url': None,
                        'branches': { 'master': ("a"*40, "b"*40) }
                       }
            
            push.side_effect = [expected, git.PushFailure, expected]
            actual = subject.push(None)
            self.assertEqual(expected, actual)


