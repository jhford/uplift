import unittest

import gaia_uplift.reporting as subject


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
        expected = 'a a a...'
        actual = subject.trim_words(s, 9)
        self.assertEqual(expected, actual)
