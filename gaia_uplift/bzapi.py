#!/usr/bin/env python

import sys
import urllib
import urllib2
import urlparse
import json
import copy
import os
import time

import requests

import util

class FailedBZAPICall(Exception): pass
class InvalidBZAPICredentials(Exception): pass
class MultipleQueryParam(Exception): pass

api_version = "tip"
api_host = "https://api-dev.bugzilla.mozilla.org/%s/" % api_version

bug_db = {}

def _raw_query(method, url, attempt=1, **kwargs):
    def write_log():
        with open('uplift_api_calls.log', 'ab+') as f:
            # Scrubadubdub
            log_line['url'] = log_line['url'].replace(credentials['password'], '<password>')
            json.dump(log_line, f, indent=2)
            f.write(',\n')
            f.flush()

    log_line = {
        'url': url,
        'method': method,
        'attempt': attempt
    }

    if kwargs.has_key('data'):
        log_line['request_data'] = kwargs['data']

    t = util.time_start()
    try:
        r = requests.request(method, url, **kwargs)
    except requests.exceptions.RequestException as e:
        write_log()
        raise FailedBZAPICall(super_exception=e)
    log_line['request_time'] = util.time_end(t)
    log_line['http_status'] = r.status_code

    if r.status_code == requests.codes.ok:
        try:
            data = r.json()
        except ValueError as e:
            log_line['bzapi_error'] = 'response was not json'
            write_log()
            raise FailedBZAPICall(super_exception=e)

        if data.get('error', 0) != 0:
            log_line['bzapi_error'] = data['message']
            write_log()
            raise FailedBZAPICall(data['message'])

        write_log()
        return data
    else:
        log_line['http_error'] = r.text
        write_log()
        try:
            r.raise_for_status()
        except urllib2.HTTPError as e:
            raise FailedBZAPICall(super_exception=e)


def do_query(url, method='get', retry=False, attempts=5, delay=2, **kwargs):
    """Light wrapper around the BzAPI which takes an API url,
    fetches the data then returns the data as a Python
    dictionary.  Only API errors are caught, and those are
    raised as FailedBZAPICall exceptions"""

    for i in range(0, attempts):
        try:
            json_data = _raw_query(method, url, i+1, **kwargs)
            return json_data
        except Exception, e:
            print "Query attempt %i failed: %s" % (i, e)
            time.sleep(delay)
    raise e


def flatten_query(query):
    """Flatten a query.  Normally it's a {'key': ['val1', 'valN']} structure,
    but we want to flatten it down to "key=valN" format.  The docs in the library
    suggest that this should be handled, but it isn't"""
    fquery = {}
    for k in query.keys():
        if len(set(query[k])) != 1:
            raise MultipleQueryParam("There are duplicate query parameters.  This is always bad. No, always!")
        fquery[k] = query[k][-1]
    return fquery

def compute_url(query, endpoint):
    """This is where we assemble the query.  We add in the BZ credentials
    here so that they don't end up in other parts of the program"""
    full_query = copy.deepcopy(query)
    full_query.update(credentials)
    return "%s%s%s?%s" % (api_host, "" if api_host.endswith("/") else "/", endpoint, urllib.urlencode(full_query))


def load_credentials(credentials_file="~/.bzapi_credentials"):
    """ I know how to load a BzAPI credentials file (json dict).
    I should probably be taught how to encrypt and decrypt this info"""
    cf = os.path.expanduser(credentials_file)
    if not os.path.exists(cf) or os.path.isdir(cf):
        raise InvalidBZAPICredentials("credentials file is not found: %s" % cf)
    try:
        data = util.read_json(cf)
    except IOError as ioe:
        raise InvalidBZAPICredentials("could not read credentials file: %s" % ioe)
    if data.has_key('username') and data.has_key('password'):
        return {'username': data['username'], 'password': data['password']}
    raise InvalidBZAPICredentials("credentials file did not have a username and password")

# XXX: Notice this is in a weird place?  Yah, me too.  This sucks!
credentials = load_credentials()

def parse_bugzilla_query(url):
    """Take a URL to bugzilla.mozilla.org and convert the query into a BzAPI
    query"""
    # I hate this function
    url_parts = urlparse.urlparse(url)
    query_string = url_parts.query
    query = urlparse.parse_qs(query_string, keep_blank_values=True)
    # Remove some parameters that aren't useful in the BzAPI context 
    for p in ('list_id', 'known_name', 'columnlist', 'query_based_on', 'query_format', 'ctype'):
        if query.has_key(p):
            del query[p]

    norm = {}
    dupe = {}
    queries = []

    if len(query.keys()) == 0:
        return []

    for arg in query.keys():
        if len(set(query[arg])) > 1:
            dupe[arg] = list(set(query[arg]))
        else:
            norm[arg] = query[arg][0]

    if len(dupe.keys()) == 0:
        return [norm]

    # This algorithm is kind of bad because it visits
    # each permutation 1 time for each duplicate
    def make_queries(visited, to_visit):
        if len(to_visit) == 0:
            q = {}
            q.update(norm)
            q.update(visited)
            if q not in queries:
                queries.append(q)
        else:
            for key in to_visit.keys():
                for value in to_visit[key]:
                    new_visited = {}
                    new_visited.update(visited)
                    new_visited.update({key: value})
                    new_to_visit = {}
                    new_to_visit.update(to_visit)
                    del new_to_visit[key]
                    make_queries(new_visited, new_to_visit)

        
    make_queries({}, dupe)
    
    return queries


def parse_bzapi_url(url):
    return flatten_query(urlparse.parse_qs(urlparse.urlparse(url).query, keep_blank_values=True))


def search(query):
    """Take a BzAPI query URL, complete a BzAPI search for it then return a dictionary of information.
    The returned dict is keyed by bug number.  The field parameter is either a string or a list.
    If it's a known string (currently basic, all) then a predefined set of bug keys are return.
    If it's a list, then the keys which match items in fields are returned"""
    print "Running Bugzilla API query"
    t = util.time_start()
    data = do_query(compute_url(query, 'bug'), retry=True)
    print "API query found %d bugs in %0.2f seconds" % (len(data.get('bugs', [])), util.time_end(t))
    return [x['id'] for x in data['bugs']]


def fetch_bug(bug_id, include_fields=None):
    print "USING DEPRECATED FUNCTION!"
    return fetch_complete_bug(bug_id)


def fetch_complete_bug(bug_id):
    query = {
        'include_fields': "_default,assigned_to,comments,flags"
    }
    return do_query(compute_url(query, 'bug/'+bug_id), retry=True)

# This function is split from update_bug to make testing easier
def create_updates(bug, comment=None, values=None, flags=None):
    updates = {
        'token': bug['update_token'],
    }
    if comment:
        updates['comments'] = [{'text': comment}]
    if flags:
        updates['flags'] = flags
    if values:
        updates.update(values)
    return updates


def update_bug(bug_id, comment=None, values=None, flags=None):
    bug_data = fetch_complete_bug(bug_id)
    updates = create_updates(comment, values, flags)
    url = compute_url({}, "bug/%s" % bug_id)
    result = do_query(url, "put", data=json.dumps(updates))

