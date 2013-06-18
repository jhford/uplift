#!/bin/bash

cd gaia
git checkout -b temp
for b in v1.0.1 v1-train v1.1.0hd master ; do
    git reset --hard HEAD
    git branch -D $b
    git checkout -t origin/$b -b $b
done
git branch -D temp
