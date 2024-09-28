#!/bin/bash
mkdir -p users/madhava/madhava@openmined.org/a
echo '{"admin": ["madhava@openmined.org"], "read": ["madhava@openmined.org", "GLOBAL"], "write": ["madhava@openmined.org"], "filepath": null}' > users/madhava/madhava@openmined.org/a/_.syftperm
echo "aaa" > users/madhava/madhava@openmined.org/a/a.txt

mkdir -p users/madhava/madhava@openmined.org/a/b
ln -s users/madhava/madhava@openmined.org/a/a.txt users/madhava/madhava@openmined.org/a/b/b.txt

