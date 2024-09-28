#!/bin/sh
cp -r ./apps/$1 ./users/$2/apps/$1
rm -rf ./users/$2/apps/$1/output
rm ./users/$2/apps/$1/cache/last_run.json
