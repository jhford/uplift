import unittest
from mock import patch

import gaia_uplift.reporting as subject
import gaia_uplift.branch_logic as branch_logic


class TrimWords(unittest.TestCase):
    def test_less_than_max(self):
        expected = "a" * 5
        actual = subject.trim_words(expected, 5)
        self.assertEqual(expected, actual)
    
    def test_more_than_max(self):
        s = 'aaaaa'
        expected = 'aaa'
        actual = subject.trim_words(s, 3)
        self.assertEqual(expected, actual)

    def test_more_than_max_with_spaces(self):
        s = 'a a a a a a a a a'
        expected = 'a a a a...'
        actual = subject.trim_words(s, 9)
        self.assertEqual(expected, actual)


class ClassifyGBU(unittest.TestCase):
    def test_good(self):
        report = {
            '123456': {
                'uplift_status': {
                    'abcd123': {
                        'success': {'v1': '321dcba'},
                        'failure': []
                    }
                }
            }
        }
        expected = ['123456']
        good, bad, ugly = subject.classify_gbu(report)
        self.assertEqual(expected, good)
        self.assertEqual([], bad)
        self.assertEqual([], ugly)

    def test_bad(self):
        report = {
            '123456': {
                'uplift_status': {
                    'abcd123': {
                        'success': {},
                        'failure': ['v1']
                    }
                }
            }
        }
        expected = ['123456']
        good, bad, ugly = subject.classify_gbu(report)
        self.assertEqual(expected, bad)
        self.assertEqual([], good)
        self.assertEqual([], ugly)

    def test_ugly(self):
        report = {
            '123456': {
                'uplift_status': {
                    'abcd123': {
                        'success': {'v1': '321dcba'},
                        'failure': ['v2']
                    }
                }
            }
        }
        expected = ['123456']
        good, bad, ugly = subject.classify_gbu(report)
        self.assertEqual(expected, ugly)
        self.assertEqual([], good)
        self.assertEqual([], bad)

class MakeNeedInfo(unittest.TestCase):
    def test_assingee(self):
        bug_data = {
            'assigned_to': {
                'name': 'testuser'
            }
        }
        expected = [{
            'name': 'needinfo',
            'requestee': {
                'name': 'testuser'
            },
            'status': '?',
            'type_id': '800'
        }]
        actual = subject.make_needinfo(bug_data)
        self.assertEqual(expected, actual)
    
    def test_fallback(self):
        bug_data = {
            'assigned_to': {
                'name': 'nobody@mozilla.org'
            },
            'creator': {
                'name': 'testuser'
            }
        }
        expected = [{
            'name': 'needinfo',
            'requestee': {
                'name': 'testuser'
            },
            'status': '?',
            'type_id': '800'
        }]
        actual = subject.make_needinfo(bug_data)
        self.assertEqual(expected, actual)

class GoodBugComment(unittest.TestCase):
    def test_success(self):
        bug = {
            'commits': ['abcd123'],
            'needed_on': ['v1'],
            'already_fixed_on': [],
            'flags_to_set': {
                'v1-status': 'fixed'
            },
            'uplift_status': {
                'abcd123': {
                    'success': {'v1': '321dcba'},
                    'failure': []
                }
            }
        }
        msg = subject.generate_good_bug_msg(bug)
        self.assertIsNotNone(msg)
        with patch('gaia_uplift.bzapi.update_bug') as update_bug:
            subject.good_bug_comment(None, '123456', bug)
            update_bug.assert_called_once_with('123456', comment=msg, values=bug['flags_to_set'])

    def test_failure(self):
        bug = {
            'commits': ['abcd123'],
            'needed_on': ['v1'],
            'already_fixed_on': [],
            'flags_to_set': {
                'v1-status': 'fixed'
            },
            'uplift_status': {
                'abcd123': {
                    'success': {'v1': '321dcba'},
                    'failure': []
                }
            }
        }
        msg = subject.generate_good_bug_msg(bug)
        self.assertIsNotNone(msg)
        with patch('gaia_uplift.bzapi.update_bug') as update_bug:
            update_bug.side_effect = Exception
            with self.assertRaises(subject.FailedToComment):
                subject.good_bug_comment(None, '123456', bug)
            update_bug.assert_called_once_with('123456', comment=msg, values=bug['flags_to_set'])


class BadBugComment(unittest.TestCase):
    def test_success(self):
        bug = {
            'commits': ['abcd123'],
            'needed_on': ['v1'],
            'already_fixed_on': [],
            'flags_to_set': {
            },
            'uplift_status': {
                'abcd123': {
                    'success': {},
                    'failure': ['v1']
                }
            }
        }
        with patch('gaia_uplift.bzapi.update_bug') as update_bug, \
             patch('gaia_uplift.git.sort_commits') as sort_commits, \
             patch('gaia_uplift.bzapi.fetch_complete_bug') as fetch_bug, \
             patch('gaia_uplift.reporting.merge_script') as merge_script:
            sort_commits.return_value = ['abcd123']
            merge_script.return_value = 'a_merge_script'
            bug_data = {
                'comments': [],
                'assigned_to': {'name': 'testuser'}
            }
            fetch_bug.return_value = bug_data
            expected_flags = subject.make_needinfo(bug_data)
            msg = subject.generate_bad_bug_msg(None, bug)
            self.assertIsNotNone(msg)
            subject.bad_bug_comment(None, '123456', bug)
            update_bug.assert_called_once_with(
                '123456', comment=msg, values=bug['flags_to_set'], flags=expected_flags)

    def test_failure(self):
        bug = {
            'commits': ['abcd123'],
            'needed_on': ['v1'],
            'already_fixed_on': [],
            'flags_to_set': {
            },
            'uplift_status': {
                'abcd123': {
                    'success': {},
                    'failure': ['v1']
                }
            }
        }
        with patch('gaia_uplift.bzapi.update_bug') as update_bug, \
             patch('gaia_uplift.git.sort_commits') as sort_commits, \
             patch('gaia_uplift.bzapi.fetch_complete_bug') as fetch_bug, \
             patch('gaia_uplift.reporting.merge_script') as merge_script:
            sort_commits.return_value = ['abcd123']
            merge_script.return_value = 'a_merge_script'
            bug_data = {
                'comments': [],
                'assigned_to': {'name': 'testuser'}
            }
            fetch_bug.return_value = bug_data
            expected_flags = subject.make_needinfo(bug_data)
            msg = subject.generate_bad_bug_msg(None, bug)
            self.assertIsNotNone(msg)
            update_bug.side_effect = Exception
            with self.assertRaises(subject.FailedToComment):
                subject.bad_bug_comment(None, '123456', bug)
            update_bug.assert_called_once_with(
                '123456', comment=msg, values=bug['flags_to_set'], flags=expected_flags)

    def test_short_circuit(self):
        bug_data = {
            'comments': [
                {'text': 'git cherry-pick'}
            ]
        }
        with patch('gaia_uplift.bzapi.fetch_complete_bug') as fetch_bug:
            fetch_bug.return_value = bug_data
            self.assertIsNone(subject.bad_bug_comment(None, '123456', {}))


class UglyBugComment(unittest.TestCase):
    def test_success(self):
        bug = {
            'commits': ['abcd123'],
            'needed_on': ['v1', 'v2'],
            'already_fixed_on': [],
            'flags_to_set': {
                'v1-status': 'fixed'
            },
            'uplift_status': {
                'abcd123': {
                    'success': {'v1': '321dcba'},
                    'failure': ['v2']
                }
            }
        }
        with patch('gaia_uplift.bzapi.update_bug') as update_bug, \
             patch('gaia_uplift.git.sort_commits') as sort_commits, \
             patch('gaia_uplift.bzapi.fetch_complete_bug') as fetch_bug, \
             patch('gaia_uplift.reporting.merge_script') as merge_script:
            bug_data = {
                'comments': [],
                'assigned_to': {'name': 'testuser'}
            }
            fetch_bug.return_value = bug_data
            merge_script.return_value = 'a_merge_script'
            msg = subject.generate_ugly_bug_msg(bug)
            self.assertIsNotNone(msg)
            subject.ugly_bug_comment(None, '123456', bug)
            expected_flags = subject.make_needinfo(bug_data)
            update_bug.assert_called_once_with(
                '123456', comment=msg, values=bug['flags_to_set'], flags=expected_flags)

