#!/bin/bash

set -ex

GAIA_REMOTE=github.com:mozilla-b2g/gaia.git

# Update the reference repository
if [[ ! -d gaia.git ]] ; then
    git clone --mirror "$GAIA_REMOTE" gaia.git
else
    (cd gaia.git && git fetch origin)
fi

# Create and fix up the local copy of Gaia
git clone file://$PWD/gaia.git gaia
(
    cd gaia &&
    git remote rm origin && 
    git remote add origin "$GAIA_REMOTE" &&
    git fetch origin
)

# Create the branches we care about
for i in v1-train v1.0.0 v1.0.1; do
    (cd gaia && git checkout -t origin/$i -b $i)
done
(cd gaia && git checkout master)
