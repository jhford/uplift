#!/usr/bin/env python

import os
import sys
import json
try:
    import signal
    signal.signal(signal.SIGINT, signal.SIG_IGN)
except:
    print "Careful about Control-C"

import uplift
import find_commits
import merge_hd
import git
import reporting
import util
import traceback
import configuration as c

def main():
    args = sys.argv
    gaia_url = c.read_value('repository.url')
    gaia_path = os.path.join(os.getcwd(), gaia_url.split('/')[-1])

    if len(args) < 2:
        print "You must specify a command"
        exit(1)

    cmd = args[1]
    cmd_args = args[2:]

    if cmd == 'show':
        bugs = uplift.build_uplift_requirements(gaia_path)
        print "\n\nRequirements for Bug uplift:"
        print reporting.display_uplift_requirements(bugs)
    elif cmd == 'uplift':
        requirements = uplift.build_uplift_requirements(gaia_path)
        full_requirements = find_commits.for_all_bugs(gaia_path, requirements)

        print "\n\nUplift requirements:"
        print reporting.display_uplift_requirements(full_requirements)
        uplift_report = uplift.uplift(gaia_path, gaia_url, full_requirements)
        print reporting.display_uplift_report(uplift_report)
        try:
            push_info = uplift.push(gaia_path)
            if push_info:
                try:
                    reporting.comment(gaia_path, uplift_report)
                except Exception as e:
                    print "ERROR: Commenting on the bugs failed"
                    print "  Fix the error and try again with:"
                    print "  uplift comments %s" % uplift.uplift_dated_file
                    print "DEBUG INFO FOLLOWS:"
                    print e
                    traceback.print_exc()
            else:
                print "To replay the comments for this push, run:"
                print "  uplift comments %s" % uplift.uplift_dated_file
        except git.PushFailure:
            print "ERROR: Pushing failed.  Try doing another uplift, and tell it to 'reuse' commits"
            exit(1)

    elif cmd == 'update':
        git.create_gaia(gaia_path, gaia_url)
    elif cmd == 'merge':
        merge_hd.merge(gaia_path, gaia_url, cmd_args[0], cmd_args[1])
    elif cmd == 'comments':
        if len(cmd_args) == 0:
            uplift_report_file = uplift.uplift_report_file
        elif len(cmd_args) == 1 and os.path.exists(cmd_args[0]):
            uplift_report_file = os.path.abspath(cmd_args[0])
        else:
            print "ERROR: missing or too many json files"
            exit(1)
        with open(uplift_report_file, 'rb') as f:
            uplift_report = json.load(f)
        reporting.comment(gaia_path, uplift_report)

    elif cmd == 'merge-comments':
        merge_hd.comment(gaia_path, cmd_args[0], cmd_args[1])
    elif cmd == "sort-commits":
        if len(cmd_args) < 3:
            print "ERROR: You must have a branch and at least one commit to sort"
            exit(1)
        branch = cmd_args[1]
        commits = cmd_args[2:]
        print "->".join(git.sort_commits(gaia_path, commits, branch))
    else:
        print "ERROR: You did not specify a command!"
        exit(1)


if __name__ == "__main__":
    main()

