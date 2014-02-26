import unittest
import os
import json
from mock import patch
import tempfile

import gaia_uplift.git as git
import gaia_uplift.bzapi as bzapi
import gaia_uplift.uplift as subject
import gaia_uplift.configuration as c

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

class BuildUpliftRequirements(unittest.TestCase):
    def setUp(self):
        self.old_config = c.json_file
        self.config = os.path.join(os.path.dirname(__file__), 'uplift_tests_config.json')
        c.change_file(self.config)

    def tearDown(self):
        c.change_file(self.old_config)

    def test_new(self):
        old_rf = subject.requirements_file
        subject.requirements_file = os.devnull
        with patch('gaia_uplift.uplift.find_bugs') as find_bugs, \
             patch('gaia_uplift.uplift.is_skipable') as is_skipable, \
             patch('gaia_uplift.bzapi.fetch_complete_bug') as fetch_bug, \
             patch('gaia_uplift.util.ask_yn') as ask_yn:
            # This is basically a directory which we can use for the fake
            # bug data fetching
            bug_data = {
                '1': {
                    'v1-status': 'fixed',
                    'v2-status': 'verified',
                    'v3-status': 'purplemonkeydishwasher',
                    'blocking': 'v1',
                    'summary': 'bug1'
                },
                '2': {
                    'v3-status': '---',
                    'blocking': 'v3',
                    'summary': 'bug2'
                },
                '3': {
                    'v3-status': '---',
                    'blocking': '-',
                    'summary': 'bug3'
                },
                '4': {
                    'v3-status': '---',
                    'summary': 'bug4',
                    'attachments': [{'flags': [{'name': 'approval-v3', 'status': '+'}]}]
                },
                '5': {
                    'v3-status': '---',
                    'summary': 'bug5',
                    'attachments': [{'flags': [{'name': 'approval-v3','status': '-'}]}]
                },
            }
            def fetch_bugs_gen(x):
                return bug_data[x]

            # Fake returns
            ask_yn.return_value = False
            is_skipable.return_value = False
            find_bugs.return_value = bug_data.keys()
            fetch_bug.side_effect = fetch_bugs_gen
            
            expected = {
                '1': {
                    'needed_on': [u'v3'],
                    'already_fixed_on': [u'v1', u'v2'],
                    'summary': 'bug1'
                },
                '2': {
                    'needed_on': [u'v3'],
                    'already_fixed_on': [],
                    'summary': 'bug2'
                },
                '4': {
                    'needed_on': [u'v3'],
                    'already_fixed_on': [],
                    'summary': 'bug4'
                },
            }

            actual = subject.build_uplift_requirements(None)
            self.assertEqual(expected, actual)
        subject.requirements_file = old_rf

    def test_existing(self):
        with patch('gaia_uplift.util.ask_yn') as ask_yn, \
             patch('gaia_uplift.util.read_json') as read_json:
            expected = 'lemonmeranguepie'
            read_json.return_value = expected
            ask_yn.return_value = True

            actual = subject.build_uplift_requirements(None)
            self.assertEqual(expected, actual)
