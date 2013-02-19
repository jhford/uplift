#!/usr/bin/env python

import sys
import urllib
import urlparse

api_version = "1.2"
api_host = "https://api-dev.bugzilla.mozilla.org/%s/" % api_version

def convert_bz_query_to_api_query(p):
    url_parts = urlparse.urlparse(p)
    query_string = url_parts.query
    query = urlparse.parse_qs(query_string, keep_blank_values=True)
    fquery = {} # Flattened query
    for k in query.keys():
        if len(query[k]) != 1:
            print "%s has more than one value. Overwriting %s with %s" % (k, ", ".join(query[k][:-1]), query[k][-1])
        fquery[k] = query[k][-1]
    api_qs = urllib.urlencode(fquery)
    print "API URL:"
    print "="*80
    print "%s%sbug?%s" % (api_host, "" if api_host.endswith("/") else "/", api_qs)
    print "="*80

if __name__ == "__main__":
    for arg in sys.argv[1:]:
        convert_bz_query_to_api_query(arg)
