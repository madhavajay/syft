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

# Function to check if a directory exists
check_directory() {
    local dir_path="$1"
    if [ -d "$dir_path" ]; then
        return 0
    else
        return 1
    fi
}

# Function to check if a file exists in a directory
check_file() {
    local dir_path="$1"
    local filename="$2"
    if [ -f "$dir_path/$filename" ]; then
        return 0
    else
        return 1
    fi
}

zip_folder() {
    local folder_path="$1"     # The path to the folder you want to zip
    local zip_name="$2"        # The desired name of the zip file
    local timestamp=$(date +"%Y%m%d_%H%M%S")

    echo "Zipping folder '$folder_path' as '$zip_name.zip'..."

    # Check if the folder exists
    if [ -d "$folder_path" ]; then
        # Zip the folder
        zip -r "${zip_name}_${timestamp}.zip" "$folder_path"
        echo "Folder '$folder_path' has been zipped as '$zip_name.zip'."
    else
        echo "Error: Folder '$folder_path' does not exist."
        exit 1
    fi
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

post_ring_check() {
    local end_user="$1"
    local status=0

    echo -e "Checking ring data for user: $end_user"

    # Get pipeline path
    _pipeline="$CLIENT_DIR/$end_user/$end_user@openmined.org/app_pipelines/ring/done"

    echo -e "Checking ring results for user: $_pipeline"

    # Check pipeline directory
    if ! check_directory "$_pipeline"; then
        echo -e "Error >> Ring app result is not ready: Done pipeline directory not found"
        status=1
    fi

    # Check data file
    local data_file="data.json"
    if ! check_file "$_pipeline" "$data_file"; then
        echo -e "Error >> Ring app result not found: $data_file not found in pipeline directory"
        status=1
    fi

    # Zip the logs if the check fails
    if [ $status -eq 1 ]; then
        # If check returns 1 (failure), zip the logs
        zip_folder "$E2E_DIR" "ring-e2e"
        return 1
    fi

    echo -e "Success !! Ring app result is ready: Done pipeline directory and data file found."
    return 0
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

    # check ring results
    post_ring_check user1

}

trap cleanup SIGINT EXIT TERM
do_e2e "$@"
