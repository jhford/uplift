#!/bin/bash

set -e

cd gaia
git fetch origin
for b in v1.0.1 v1-train v1.1.0hd master ; do
    git reset --hard HEAD
    git checkout $b
    git merge --ff-only origin/$b
done
echo Doing a dry run push to make sure that the repo is sane
git push -n origin
