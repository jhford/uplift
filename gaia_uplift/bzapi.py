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

api_version = "tip"
api_host = "https://api-dev.bugzilla.mozilla.org/%s/" % api_version


def _raw_query(method, url, **kwargs):
    r = requests.request(method, url, **kwargs)
    with open('api-calls.log', "ab+") as f:
        f.write("Status: %i URL: %s %s\n" % (r.status_code, method, url))
        if kwargs.has_key('data'):
            f.write("DATA\n%s\n" % json.dumps(kwargs['data']))
        if r.status_code == requests.codes.ok:
            data = r.json()
            if data.get('error', 0) != 0:
                f.write("BZAPI ERROR:\n%s\n" % data['error'])
                raise FailedBZAPICall(data['message'])
            return data
        else:
            f.write("ERROR: %s\n" % r.text)
            r.raise_for_status()


def do_query(url, method='get', retry=False, attempts=5, delay=2, **kwargs):
    """Light wrapper around the BzAPI which takes an API url,
    fetches the data then returns the data as a Python
    dictionary.  Only API errors are caught, and those are
    raised as FailedBZAPICall exceptions"""

    for i in range(0, attempts):
        try:
            json_data = _raw_query(method, url, **kwargs)
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
        if len(query[k]) != 1:
            print >> sys.stderr, "%s has more than one value. Overwriting %s with %s" % (k, ", ".join(query[k][:-1]), query[k][-1])
        fquery[k] = query[k][-1]
    return fquery

def compute_url(query, endpoint):
    """This is where we assemble the query.  We add in the BZ credentials
    here so that they don't end up in other parts of the program"""
    full_query = copy.deepcopy(query)
    full_query.update(load_credentials())
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


def parse_bugzilla_query(url):
    """Take a URL to bugzilla.mozilla.org and convert the query into a BzAPI
    query.  The optional dictionary 'override_qs' is a key value mapping of
    query string parameters that will be overwritten in the output url"""
    url_parts = urlparse.urlparse(url)
    query_string = url_parts.query
    query = urlparse.parse_qs(query_string, keep_blank_values=True)
    fquery = flatten_query(query)
    # Remove some parameters that aren't useful in the BzAPI context 
    for p in ('list_id', 'known_name', 'columnlist', 'query_based_on', 'query_format', 'ctype'):
        if fquery.has_key(p):
            del fquery[p]
    return fquery


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
    query = {}
    if include_fields:
        query['include_fields'] = include_fields
    t = util.time_start()
    bug_data = do_query(compute_url(query, 'bug/%s' % bug_id), retry=True)
    print "Fetched bug %s in %0.2f seconds" % (bug_id, util.time_end(t))
    return bug_data


def fetch_complete_bug(bug_id):
    return fetch_bug(bug_id, "_default,assigned_to,comments,flags")

def update_bug(bug_id, comment=None, values=None, flags=None):
    bug_data = fetch_complete_bug(bug_id)
    updates = {
        'token': bug_data['update_token'],
    }
    if comment:
        updates['comments'] = [{'text': comment}]
    if flags:
        updates['flags'] = flags
    if values:
        updates.update(values)
    url = compute_url({}, "bug/%s" % bug_id)
    result = do_query(url, "put", data=json.dumps(updates))

