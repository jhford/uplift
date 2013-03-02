#!/usr/bin/env python

import os
import sys

import uplift
import reporting


gaia_path = os.path.abspath(os.path.join(os.getcwd(), 'uplift-gaia'))
gaia_url = "github.com:mozilla-b2g/gaia.git"
query_file = os.path.abspath("uplift_queries.dat")


def main():
    with open(query_file, 'rb') as f:
        queries = [x.strip() for x in f.readlines()]

    if len(sys.argv) < 2:
        print "You must specify a command"
        exit(1)

    cmd = sys.argv[1]
    cmd_args = sys.argv[1:]

    if cmd == 'show':
        bugs = uplift.build_uplift_requirements(gaia_path, queries)
        print "\n\nRequirements for Bug uplift:"
        print reporting.display_uplift_requirements(bugs)
    elif cmd == 'uplift':
        requirements = uplift.build_uplift_requirements(gaia_path, queries)
        print "\n\nUplift requirements:"
        print reporting.display_uplift_requirements(requirements)
        uplift_report = uplift.uplift(gaia_path, gaia_url, requirements)
        print reporting.display_uplift_report(uplift_report)
        print reporting.display_uplift_comments(gaia_path, uplift_report)


if __name__ == "__main__":
    main()

