import unittest
import os
import copy
import gaia_uplift.bzapi as subject
import gaia_uplift.configuration as c
from mock import patch
import urllib2
import requests



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
        expected = '%ssample?username=test_user%%40bugzilla.com&password=testpassword'
        self.assertEqual(expected % c.read_value('bugzilla.api.host'), url)

    def test_simple_query(self):
        url = subject.compute_url({'a': 'b'}, 'sample')
        expected = '%ssample?a=b&username=test_user%%40bugzilla.com&password=testpassword'
        self.assertEqual(expected % c.read_value('bugzilla.api.host'), url)


class ParseBugzillaQuery(BZAPITest):
    def test_no_params(self):
        url = 'http://b.m.o/search'
        queries = subject.parse_bugzilla_query(url)
        self.assertEqual([], queries)
    
    def test_no_duplicates(self):
        url = 'http://b.m.o/search?a=b&c=d'
        queries = subject.parse_bugzilla_query(url)
        self.assertEqual(1, len(queries))
        self.assertEqual(sorted([{'a': 'b', 'c': 'd'}]), sorted(queries))

    def test_single_duplicate_one_norm(self):
        url = 'http://b.m.o/search?a=b&a=c&d=e'
        queries = subject.parse_bugzilla_query(url)
        self.assertEqual(2, len(queries))
        self.assertEqual(sorted([{'a': 'b', 'd': 'e'}, {'a': 'c', 'd': 'e'}]),
                         sorted(queries))

    def test_single_duplicate(self):
        url = 'http://b.m.o/search?a=b&a=c'
        queries = subject.parse_bugzilla_query(url)
        self.assertEqual(2, len(queries))
        self.assertEqual(sorted([{'a': 'b'}, {'a': 'c'}]),
                         sorted(queries))
        
    def test_two_duplicates(self):
        url = 'http://b.m.o/search?a=b&a=c&d=e&d=f'
        queries = subject.parse_bugzilla_query(url)
        self.assertEqual(4, len(queries))
        expected = [
            {'a': 'b', 'd': 'e'},
            {'a': 'b', 'd': 'f'},
            {'a': 'c', 'd': 'e'},
            {'a': 'c', 'd': 'f'}
        ]
        self.assertEqual(sorted(expected), sorted(queries))

class CreateUpdates(BZAPITest):
    def test_invalid_call(self):
        with self.assertRaises(AssertionError):
            subject.create_updates('i am a string')

    def test_no_updates(self):
        token = 'abc123'
        bug_data = {'update_token': token}
        updates = subject.create_updates(bug_data)
        self.assertEqual({'token': token}, updates)

    def test_updates(self):
        token = 'abc123'
        comment = 'hello'
        flags  = [{'name': 'awesome', 'status': '+'}]
        values = {'blocking': 'v1'}
        bug_data = {'update_token': token}
        updates = subject.create_updates(bug_data, comment=comment, flags=flags, values=values)
        expected = {
            'token': token,
            'comments': [{'text': comment}],
            'flags': flags,
            'blocking': 'v1'
        }
        self.assertEqual(expected, updates)

class RawQuery(unittest.TestCase):
    def setUp(self):
        subject.credentials = subject.load_credentials(os.path.abspath(os.path.join(os.path.dirname(__file__), 'test_cred')))

    def test_success(self):
        expected = {'hello': 'hi'}

        class SuccessResponse():
            status_code = 200
            def json(self):
                return {'hello': 'hi'}

        with patch('requests.request') as request:
            request.return_value = SuccessResponse()

            actual = subject._raw_query('get', 'http://www.google.com/')
            
            self.assertEqual(expected, actual)

    def test_request_fails(self):
        with patch('requests.request') as request:
            request.side_effect = requests.exceptions.RequestException
            with self.assertRaises(subject.FailedBZAPICall):
                subject._raw_query('get', 'http://www.google.com/')

    def test_bad_json(self):
        class BadJson():
            status_code = 200
            def json(self):
                raise ValueError
        with patch('requests.request') as request:
            request.return_value = BadJson()
            with self.assertRaises(subject.FailedBZAPICall):
                subject._raw_query('get', 'http://www.google.com/')
            
    def test_bzapi_internal_error(self):
        class ApiError():
            status_code = 200
            def json(self):
                return {'error': 1, 'message': 'fake error'}
        with patch('requests.request') as request:
            request.return_value = ApiError()
            with self.assertRaises(subject.FailedBZAPICall):
                subject._raw_query('get', 'http://www.google.com/')

    def test_bad_status_code(self):
        class BadStatus():
            status_code = 404
            text = 'bad status code'
            def json(self):
                return {'hello': 'hi'}
            def raise_for_status(self):
                raise urllib2.HTTPError(
                    'http://www.google.com',
                    404,
                    'a bad code',
                    {},
                    None)
        with patch('requests.request') as request:
            request.return_value = BadStatus()
            with self.assertRaises(subject.FailedBZAPICall):
                subject._raw_query('get', 'http://www.google.com/')
    
