#!/usr/bin/env python

import os
import sys
import json
try:
    import signal
    print "Ignoring Control-C"
    signal.signal(signal.SIGINT, signal.SIG_IGN)
except:
    print "Careful about Control-C"

import uplift
import merge_hd
import git
import reporting
import util
import configuration as c

def main():
    args = sys.argv

    enabled_branches = c.read_value('repository.enabled_branches')
    config_queries = c.read_value('queries')
    gaia_url = c.read_value('repository.url')

    gaia_path = gaia_url.split('/')[-1]

    queries = []
    for branch in enabled_branches:
        queries.extend(config_queries.get(branch, []))

    if len(args) < 2:
        print "You must specify a command"
        exit(1)

    cmd = args[1]
    cmd_args = args[2:]

    if cmd == 'show':
        bugs = uplift.build_uplift_requirements(gaia_path, queries)
        print "\n\nRequirements for Bug uplift:"
        print reporting.display_uplift_requirements(bugs)
    elif cmd == 'uplift':
        requirements = uplift.build_uplift_requirements(gaia_path, queries)
        print "\n\nUplift requirements:"
        print reporting.display_uplift_requirements(requirements)
        uplift_report = uplift.uplift(gaia_path, gaia_url, requirements)
        with open("log", "ab+") as l:
            l.write("STARTING_NEW_UPLIFT\n")
            l.write("==" * 80)
            l.write("\n\n")
            for f in (sys.stdout, l):
                print >> f, reporting.display_uplift_report(uplift_report)
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

    elif cmd == 'update':
        t=util.time_start()        
        if os.path.exists(gaia_path):
            print "Updating Gaia"
            git.update_gaia(gaia_path, gaia_url)
            print "Updated Gaia in %0.2f seconds" % util.time_end(t)
        else:
            print "Creating Gaia"
            git.create_gaia(gaia_path, gaia_url) # This is sadly broken
            print "Created Gaia in %0.2f seconds" % util.time_end(t)
    elif cmd == 'merge':
        merge_hd.merge(gaia_path, gaia_url, cmd_args[0], cmd_args[1])
    elif cmd == 'comments':
        with open(uplift.uplift_report_file, 'rb') as f:
            uplift_report = json.load(f)
        reporting.comment(gaia_path, uplift_report)
    elif cmd == 'merge-comments':
        merge_hd.comment(gaia_path, cmd_args[0], cmd_args[1])
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
    else:
        print "ERROR: You did not specify a command!"
        exit(1)


if __name__ == "__main__":
    main()

