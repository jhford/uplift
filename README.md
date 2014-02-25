# Background
This tool was initially written to make our branch landing strategy as painless
as possible.  It started as a bash script, then progressed into a very basic
python script.  Then it turned into a much better python script during an
extensive rewrite.  Then it was basically rewritten again and unit tests were
added to make sure that other people could use and contribute to this tool.

A lot of design decisions in this script were fine when it was a simple script
but are now a bit of a pain to work with.  I intend to fix some of these issues
as time permits, but patches are always welcome.  Please remember when looking
at this code that it was written to make incremental improvements to a
previously mind-numbing manual task while focusing on other projects.

# Usage
The basic flow of this program is:

1. gather the requirements for an uplift (see <code>gaia_uplift.uplift</code>)
1. find the commits that are needed for each bug needing uplift (see <code>gaia_uplift.find_commits</code>)
1. determine which branches each commit is needed on (see <code>gaia_uplift.branch_logic</code>)
1. cherry-pick commits onto the appropriate branches (see <code>gaia_uplift.uplift</code>)
1. push new cherry-picked commits to the remote (see <code>gaia_uplift.uplift</code>)
1. comment on and set flags for each bug that has an uplift (see <code>gaia_uplift.reporting</code>)

There is also an alternate flow for branches which use merges instead of cherry-picks.  

1. (optionally) attempt a merge
1. look at the list of new commits on the branch and try to find bug numbers
1. comment on the bugs with commits and set flags

The requirements are saved into a JSON

# Subcommands

Like many tools (git, gcc, etc) this program is implemented as a collection of subcommands to the
uplift driver program called <code>uplift</code>.  The important subcommands are:

* <code>show</code>: this command takes no arguments.  It does the requirement gathering stage of an uplift
* <code>uplift</code>: this command takes no arguments.  See the section called 'finding commits' for details
* <code>comments</code>: this command uses the data in <code>uplift_report.json</code> to replay the commenting
and flag setting.  Useful if there is a bug in the commenting code and you need to retry *just* the comments
* <code>update</code>: use the uplift program's logic to recreate a clean slate of Gaia using the cached Gaia
* <code>merge to-branch from-branch</code>: checkout out to-branch and merge in from-branch.  This will 
automatically comment on the bug numbers found in the range of commits pushed into to-branch
* <code>merge-comments to-branch commit-range</code>: like the comments command above, just comment on bugs.  The commit-range argument is the thing that the git push command outputs in the form aaaaaaaa..bbbbbbbb

# Finding commits
This is the reason that we need a human in this process.  There is currently no
standardized system in bugzilla for storing the commit that fixed the bug.  The
known methods include:

* link to the <code>github.com/mozilla-b2g/gaia.git</code> commit
* a string like "master: abcd123" which is implied to be a master commit on <code>mozilla-b2g/gaia.git</code>
* similar to the above, but referencing the patch author's person remote instead of mozilla-b2g's
* link to a merged pull request as a bug comment
* link to a pull request that's been merged as an attachment
* html attachment that does a redirect to a github pull request
* a response to a complicated set of email/irc exchanges trying to coax the information from the lander

I have written a basic heuristic to find commits, but it's *by no means
robust*.  Please consider the guessing system as an aid to reduce the amount of
copy and paste mistakes.

Once the program has the list of bugs that you need to figure out, you'll be
presented with a list of commands, guesses and an input field.  The commands
should be explained with up-to-date information in the program, but in general
you'll experience:

1. a browser window will open for the bug
1. you'll inspect the guesses (if any) and make sure that the guessed commit is actually what should
be uplifted.  Do a sanity check on the bug.  The uplift program will make sure that the commit entered
is on a valid branch and is a valid commit.
1. either accept a guess or copy and paste a commit id from the browser to the program.  Links
to github.com commits also work (makes it easy to copy link location, or drag a link over)
1. if the bug is showing up in the uplift requirements but is clearly not appropriate for gaia uplift,
you can skip it permanently with the skip command
1. when you've found all needed commits, type done.  If there are no appropriate commits, just type done
to say that you didn't find any commits

The program will move onto the next bug.

# Common issues
Problem: The program dies midway through finding commits

Solution: re-run <code>uplift uplift</code> and when asked to reuse, add or delete select the add option

Problem: The program dies after finding commits but before pushing the new commits

Solution: re-run <code>uplift uplift</code> and when asked to reuse, add or delete select the reuse option

Problem: The program dies during a push and nothing was pushed

Solution: re-run <code>uplift uplift</code> and when asked to reuse, add or delete select the add option

Problem: The program dies after a push but the push was successful

Solution: Use <code>uplift comments</code> to redo comments.  Make sure you don't redo the uplift

Problem: my push succeeded but commenting died and I re-did the uplift and lost my commits for commenting

Solution: There is a filed called <code>uplift_outcome_datestamp.json</code> that stores
the same contents as the uplift_report.json file that the <code>comments</code> command uses.  Copy
the correct <code>uplift_outcome_datestamp.json</code> to be <code>uplift_report.json</code>

# Important notes
You are modifying one of Github's most active repositories.  This repository
and the branches that you are working on are what gets put on shipping phones.
You are needed in this process because we don't have a standardised method to
store which commits should be uplifted.  If you have experience doing uplifts
for Gecko, please use the same discretion you use for it.

The biggest specific warning that I have is that once you say "yes, push these
commits" you should not rerun the uplift process until *all* the bugs in
<code>uplift_report.json</code> have been commented on and their flags set.  If
you do try to rerun the uplift, you're going to find that none of the uplifts
work properly and the bugzilla comments will incorrectly say that the commit
was already on the branch.

## Setup

Currently, this tool does not support installation through pip/pypi.  This is a
known defect and may get resolved some time.  The way that this tool is used by
the author is to create a virtualenv and run the tool in that environment.

    /**
     * Create the uplift environment.
     */
    git clone http://github.com/jhford/uplift.git uplift && cd uplift
    virtualenv .
    python setup.py develop

If you are getting import errors, try manually installing the runtime dependencies.
    
    cd uplift
    source bin/activate
    pip install pip install isodate requests PrettyTable


## Running uplift

    /**
     * Initialize the uplift environment.
     */
    source bin/activate
    uplift uplift

## Contributing
I'm more than happy to review and land potential fixes.

These things make your submission more likely to be accepted:

* complete tests.
* small, logical patches
* using good libraries where necessary
* using python3 compatible libraries
* avoiding modules with C dependencies
* pep8 compliance
* underscore method naming

These things make your submission less likely to be accepted:

* major rewrites which aren't thoroughly tested
* large patches
* code that doesn't appear visually similar to existing code
* making code messier than it already is

Issues will be tracked in the github issue tracker

You should always run unit tests with <code>make test</code>.  Only hosers don't run unit tests
