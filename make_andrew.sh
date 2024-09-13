#!/bin/bash

OWNER=andrew
OTHER=madhava

TOP_PERM_FILE='{"admin": ["'$OWNER'@openmined.org"], "read": ["'$OWNER'@openmined.org", "GLOBAL"], "write": ["'$OWNER'@openmined.org"], "filepath": null}'
PRIVATE_PERM_FILE='{"admin": ["'$OWNER'@openmined.org"], "read": ["'$OWNER'@openmined.org"], "write": ["'$OWNER'@openmined.org"], "filepath": null}'
SHARED_PERM_FILE='{"admin": ["'$OWNER'@openmined.org"], "read": ["'$OWNER'@openmined.org", "'$OTHER'@openmined.org"], "write": ["'$OWNER'@openmined.org", "'$OTHER'@openmined.org"], "filepath": null}'

# make dir
mkdir -p users/$OWNER/$OWNER@openmined.org

# make top level perm file
echo $TOP_PERM_FILE > users/$OWNER/$OWNER@openmined.org/_.syftperm

### PUBLIC
# make public folder
mkdir -p users/$OWNER/$OWNER@openmined.org/public
# add netflix mock
touch users/$OWNER/$OWNER@openmined.org/public/andrew_netflix_mock.csv


### PRIVATE
# create private dir
mkdir -p users/$OWNER/$OWNER@openmined.org/private
# create private perm file
echo $PRIVATE_PERM_FILE > users/$OWNER/$OWNER@openmined.org/private/_.syftperm
# add secret key
touch users/$OWNER/$OWNER@openmined.org/private/secret.key

### SHARED
# create shared dir
mkdir -p users/$OWNER/$OWNER@openmined.org/shared
# create shared perm file
echo $SHARED_PERM_FILE > users/$OWNER/$OWNER@openmined.org/shared/_.syftperm
# add chat txt
touch users/$OWNER/$OWNER@openmined.org/shared/chat.txt
