#!/bin/bash

set -e

SCRIPT_DIR=$(dirname $0)
ROOT_DIR=$(pwd)
E2E_DIR=$ROOT_DIR/.e2e
RING_DIR=$E2E_DIR/ring
LOGS_DIR=$RING_DIR/logs
CLIENT_DIR=$RING_DIR/client
CONFIG_DIR=$RING_DIR/config

pids=( )

# define cleanup function
cleanup() {
    for pid in "${pids[@]}"
    do
        echo "Killing $pid"
        kill -0 "$pid" && kill "$pid" # kill process only if it's still running
    done
}

start_client() {
    user=$1
    port=$2
    email="$1@openmined.org"

    syftbox client \
        --config_path=$CONFIG_DIR/$1.json \
        --sync_folder=$CLIENT_DIR/$1 \
        --email=$email \
        --port=$port \
        --server=http://localhost:5001 &> $LOGS_DIR/client.$1.log & pids+=($!)

}

start_server() {
    cd $RING_DIR
    syftbox server --port 5001 &> $LOGS_DIR/server.log & pids+=($!)
    cd $ROOT_DIR
}


copy_secret() {
    user=$1
    _app="$CLIENT_DIR/$user/apps/ring"

    echo "Waiting for $_app to be ready"
    while [ ! -d $_app ]
    do sleep 5
    done

    echo "$_app is ready. Copying secret!"
    cp $SCRIPT_DIR/ringdata/secret.$user.txt $_app/secret.txt
}

ring_init() {
    init_user=$1

    for user in $@
    do copy_secret $user
    done

    # loop if dir exists
    _pipeline="$CLIENT_DIR/$init_user/$init_user@openmined.org/app_pipelines/ring/running"

    echo "Waiting for $_pipeline to be ready"
    while [ ! -d $_pipeline ]
    do sleep 5
    done

    echo "$_pipeline is ready. Kick starting ring!"
    cp $SCRIPT_DIR/ringdata/init.json $_pipeline/data.json
}

do_e2e() {
    just reset
    # just install
    mkdir -p $LOGS_DIR $CONFIG_DIR $CLIENT_DIR

    echo "Starting server"
    start_server

    echo "Waiting for server to be ready"
    sleep 5

    echo "Starting clients"
    start_client user1 8080
    start_client user2 8081

    echo Kickstarting ring
    ring_init user1 user2

    # expect to finish within the timeframe
    sleep 120
}

trap cleanup SIGINT EXIT TERM
do_e2e "$@"
