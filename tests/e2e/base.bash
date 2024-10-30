#!/bin/bash

PWD=$(pwd)
E2E_DIR=$PWD/.e2e

boldwhite='\033[1;37m'
red='\033[1;31m'
yellow='\033[0;33m'
cyan='\033[1;36m'
green='\033[1;32m'
gray='\033[0;30m'
reset='\033[0m'

pids=( )

err() {
    echo -e "${red}ERROR: ${boldwhite}$1${reset}" >&2
    exit 1
}

info() {
    echo -e "${cyan}$1${reset}"
}

warn() {
    echo -e "${yellow}$1${reset}"
}

debug() {
    echo -e "${gray}$1${reset}"
}

success() {
    echo -e "${green}$1${reset}"
}

check_cmd() {
    command -v "$1" > /dev/null 2>&1
    return $?
}

need_cmd() {
    if ! check_cmd "$1"
    then err "need '$1' (command not found)"
    fi
}

########## Concurrent processes management ##########

cleanup() {
    for pid in "${pids[@]}"
    do
        # if the process is still running, kill it
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || echo "Failed to kill $pid"
        fi
    done
}

trap cleanup SIGINT EXIT TERM

run_bg() {
    "$@" & # Run the command in background
    pids+=($!) # Store the pid
}


########## Helpers ##########

wait_for_path() {
    local path="$1"
    local timeout=${2:-30}  # Default 30s timeout
    local interval=${3:-1}  # Default 1s polling interval
    local start_time=$(date +%s)

    debug "Waiting for: $path timeout=${timeout}s"

    while [ ! -e "$path" ]; do
        current_time=$(date +%s)
        elapsed=$((current_time - start_time))

        if [ $elapsed -ge $timeout ]; then
            err "Timeout after ${timeout}s waiting for: $path"
            return 1
        fi
        sleep $interval
    done

    debug "Found: $path (after ${elapsed}s)"
    return 0
}

wait_for_url() {
    local url="$1"
    local timeout=${2:-30}
    local start_time=$(date +%s)

    while ! curl -s -f "$url" > /dev/null; do
        if [ $(($(date +%s) - start_time)) -ge "$timeout" ]; then
            echo "Timeout waiting for $url"
            return 1
        fi
        sleep 1
    done
}

wait_for_server() {
    local port=${1-8080}
    local timeout=${2:-30}

    debug "Waiting for server to be read on port=$port"
    wait_for_url "http://localhost:$port/info" $timeout
}

wait_for_client() {
    local port=${1-8080}
    local timeout=${2:-30}

    debug "Waiting for client to be ready on port=$port"
    wait_for_url "http://localhost:$port/datasites" $timeout
}
