import unittest
import copy
import gaia_uplift.configuration as subject


class TestLookup(unittest.TestCase):
    def test_single_level_present(self):
        a = {'john': 'ford'}
        self.assertEqual(subject.lookup('john', a), 'ford')

    def test_single_level_absent(self):
        a = {}
        with self.assertRaises(KeyError):
            subject.lookup('john', a)

    def test_multi_level_present(self):
        a = {'john': {'harrison': {'ford': 69}}}
        self.assertEqual(subject.lookup('john.harrison.ford', a), 69)

    def test_multi_level_absent(self):
        a = {}
        with self.assertRaises(KeyError):
            subject.lookup('john.harrison.ford', a)

    def test_multi_level_partial_key(self):
        a = {'john': {'steven'}}
        with self.assertRaises(KeyError):
            subject.lookup('john.harrison.ford', a)

    def test_multi_level_bad_intermediate_key(self):
        a = {'john': 69}
        with self.assertRaises(KeyError):
            subject.lookup('john.harrison.ford', a)

class TestPresent(unittest.TestCase):
    def test_is_present(self):
        a = {'john': 'ford'}
        self.assertTrue(subject.present('john', a))

    def test_is_not_present(self):
        a = {'john': 'ford'}
        self.assertFalse(subject.present('rob', a))

class TestStore(unittest.TestCase):
    def test_single_level_store_empty(self):
        a = {}
        ex = {'john': 'ford'}
        subject.store('john', 'ford', a)
        self.assertEqual(ex, a)

    def test_single_level_store_overwrite(self):
        a = {'john': 'notford'}
        ex = {'john': 'ford'}
        subject.store('john', 'ford', a)
        self.assertEqual(ex, a)

    def test_multi_level_store_empty(self):
        a = {'john': {'harrison': {'ford': 69}}}
        ex = copy.deepcopy(a)
        ex['john']['harrison']['ford'] = 96
        subject.store('john.harrison.ford', 96, a)
        self.assertEqual(ex, a)

    def test_multi_level_store_int_intermediate_key(self):
        a = {'john': 69}
        with self.assertRaises(KeyError):
            subject.store('john.harrison.ford', 96, a)

    def test_multi_level_store_partial_key(self):
        a = {'john': {}}
        ex = copy.deepcopy(a)
        ex['john'] = {'harrison': {'ford': 69}}
        subject.store('john.harrison.ford', 69, a)
        self.assertEqual(ex, a)

