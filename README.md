
# Uplift

## Setting up environment with virtualenv

// TODO: Add some guidance for env config

## Running uplift

    /**
     * Initialize the uplift environment.
     */
    source bin/activate

    /**
     * Fetch all gaia bugs marked for uplift from
     * the bugzilla server, display them,
     * and then cache them locally.
     */
    uplift show

    /**
     * Start the uplift. You'll be asked whether or not you want to
     * use the bug list cached from uplift show; doing so will save us
     * a bit of time :).
     *
     * uplift uplift needs to first fetch gaia from github so that we
     * can merge commits into the v1 branches locally.
     *
     * For each of the bugs we fetched, we'll see a list of options:
     *
     * guess - Look at the bug in bugzilla and try to guess shasug
     *     for all of the git commits we need to uplift.
     * skip - Same as done except flags the bug locally so that we ignore
     *     it in future uplifts.
     * browser - Open the bug in bugzilla.
     * list - Display the shas we've set for uplift associated with this bug.
     * delete - Clear one or more shas we've set for uplift associated with
     *     this bug by specifying them one by one.
     * delete-all - Clear all of the shas we've set for uplift associated with
     *     this bug.
     * done - Finish associating uplift shas with this bug.
     */
    uplift uplift
