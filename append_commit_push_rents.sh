#!/bin/bash

set -eu

./scraper.py --csv >> rents.csv
git commit -am "Record rents on `date +%Y-%m%-%d`"
git push
