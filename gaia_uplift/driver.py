#!/usr/bin/env python

import os
import sys
import json

import uplift
import git
import reporting


gaia_path = os.path.abspath(os.path.join(os.getcwd(), 'gaia'))
gaia_url = "github.com:mozilla-b2g/gaia.git"
#query_file = os.path.abspath("uplift_queries.dat")
query_file = os.path.join(os.getcwd(), "uplift_queries.dat")


def main():
    with open(query_file, 'rb') as f:
        queries = [x.strip() for x in f.readlines() if not x.strip().startswith("#") and not x.strip() == ""]

    if len(sys.argv) < 2:
        print "You must specify a command"
        exit(1)

    cmd = sys.argv[1]
    cmd_args = sys.argv[1:]

    if cmd == 'show':
        bugs = uplift.build_uplift_requirements(gaia_path, queries)
        print "\n\nRequirements for Bug uplift:"
        print reporting.display_uplift_requirements(bugs)
        print "%d bugs" % len(bugs)
    elif cmd == 'uplift':
        requirements = uplift.build_uplift_requirements(gaia_path, queries)
        print "\n\nUplift requirements:"
        print reporting.display_uplift_requirements(requirements)
        print "%d bugs" % len(requirements)
        uplift_report = uplift.uplift(gaia_path, gaia_url, requirements)
        with open("log", "ab+") as l:
            l.write("STARTING_NEW_UPLIFT\n")
            l.write("==" * 80)
            l.write("\n\n")
            for f in (sys.stdout, l):
                print >> f, reporting.display_uplift_report(uplift_report)
                print "%d bugs" % len(uplift_report)
            print >> l, reporting.display_uplift_comments(gaia_path, uplift_report)

        push_info = None
        while push_info == None:
            try:
                push_info = uplift.push(gaia_path)
            except git.PushFailure:
                print "Pushing failed.  If you don't want to retry,"
                print "a lot of instructions will be printed should"
                print "you want to copy the comments over manually"
                if not util.askyn("Retry?"):
                    print reporting.display_uplift_comments(gaia_path, uplift_report)
                    break

        if push_info:
            reporting.comment(gaia_path, uplift_report)
    elif cmd == 'comments':
        with open(uplift.uplift_report_file, 'rb') as f:
            uplift_report = json.load(f)
        reporting.comment(gaia_path, uplift_report)
    elif cmd == 'reset-gaia':
        git.delete_gaia(gaia_path)
        git.create_gaia(gaia_path, gaia_url)
    elif cmd == 'update-gaia':
        git.update_gaia(gaia_path, gaia_url)
    elif cmd == "sort-commits":
        if len(cmd_args) < 3:
            print "You must have a branch and at least one commit to sort"
            exit(1)
        branch = cmd_args[1]
        commits = cmd_args[2:]
        print "->".join(git.sort_commits(gaia_path, commits, branch))



if __name__ == "__main__":
    main()

