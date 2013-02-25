#!/usr/bin/env python

import sys
import urllib
import urllib2
import urlparse
import json
import copy
import os

import util


class FailedBZAPICall(Exception): pass
class InvalidBZAPICredentials(Exception): pass

api_version = "1.2"
api_host = "https://api-dev.bugzilla.mozilla.org/%s/" % api_version



def do_query(url):
    """Light wrapper around the BzAPI which takes an API url,
    fetches the data then returns the data as a Python
    dictionary.  Only API errors are caught, and those are
    raised as FailedBZAPICall exceptions"""
    json_data = json.loads(urllib.urlopen(url).read())
    if json_data.get('error', 0) != 0:
        raise FailedBZAPICall(json_data['message'])
    return json_data


def api_call(query, endpoint, method="get"):
    opener = urllib2.build_opener(urllib2.HTTPHandler)
    if method == "get":
        request = urllib2.Request(compute_url(query, endpoint))
    elif method == "put":
        #request = urllib2.Request(
        pass


def flatten_query(query):
    fquery = {} # Flattened query
    for k in query.keys():
        if len(query[k]) != 1:
            print >> sys.stderr, "%s has more than one value. Overwriting %s with %s" % (k, ", ".join(query[k][:-1]), query[k][-1])
        fquery[k] = query[k][-1]
    return fquery

def compute_url(query, endpoint):
    full_query = copy.deepcopy(query) # Don't want to polute passed in reference with username/password
    full_query.update(load_credentials())
    return "%s%s%s?%s" % (api_host, "" if api_host.endswith("/") else "/", endpoint, urllib.urlencode(full_query))


def load_credentials(credentials_file="~/.bzapi_credentials"):
    """ I know how to load a BzAPI credentials file (json dict).
    I should probably be taught how to encrypt and decrypt this info"""
    cf = os.path.expanduser(credentials_file)
    if not os.path.exists(cf) or os.path.isdir(cf):
        raise InvalidBZAPICredentials("credentials file is not found: %s" % cf)
    try:
        with open(cf, 'rb') as f:
            data = json.load(f)
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
    data = do_query(compute_url(query, 'bug'))
    print "API query found %d bugs in %0.2f seconds" % (len(data.get('bugs', [])), util.time_end(t))
    return [x['id'] for x in data['bugs']]


def fetch_bug(bug_id):
    query = {}
    t = util.time_start()
    bug_data = do_query(compute_url(query, 'bug/%s' % bug_id))
    print "Fetched bug %s in %0.2f seconds" % (bug_id, util.time_end(t))
    return bug_data


def post_comment(bug_id, comment):
    """EXPERIMENTAL"""
    bug_data = fetch_bug(bug_id)
    update_token = bug_data['update_token']
    print update_token