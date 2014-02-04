import unittest
import os
import copy
import gaia_uplift.bzapi as subject



class BZAPITest(unittest.TestCase):
    def setUp(self):
        self.real_raw_query = subject._raw_query
        subject.credentials = subject.load_credentials(os.path.abspath(os.path.join(os.path.dirname(__file__), 'test_cred')))

    def tearDown(self):
        subject._raw_query = self.real_raw_query

class FlattenQuery(BZAPITest):
    def test_no_dupes(self):
        query = {'a': [1]}
        flattened = subject.flatten_query(query)
        self.assertEqual({'a': 1}, flattened)

    def test_someidentical_dupes(self):
        query = {'a': [1,2,1]}
        with self.assertRaises(subject.MultipleQueryParam):
            flattened = subject.flatten_query(query)

    def test_identical_dupes(self):
        query = {'a': [1,1]}
        flattened = subject.flatten_query(query)
        self.assertEqual({'a': 1}, flattened)

    def test_nonidentical_dupes(self):
        query = {'a': [1,2]}
        with self.assertRaises(subject.MultipleQueryParam):
            flattened = subject.flatten_query(query)

class ComputeUrl(BZAPITest):
    def test_doesnt_breakstuff(self):
        query = {'a': 1, 'b': 2}
        orig_query = copy.deepcopy(query)
        subject.compute_url({}, 's')
        self.assertEqual(query, orig_query)

    def test_no_query(self):
        url = subject.compute_url({}, 'sample')
        self.assertEqual('%ssample?username=test_user%%40bugzilla.com&password=testpassword' % subject.api_host, url)

    def test_simple_query(self):
        url = subject.compute_url({'a': 'b'}, 'sample')
        self.assertEqual('%ssample?a=b&username=test_user%%40bugzilla.com&password=testpassword' % subject.api_host, url)

