#! /bin/bash

set -o errexit
set -o nounset
set -o pipefail

source cicd/set_env.sh
docker login -u arjoonn -p=$DOCKER_PWD
docker build -t $1:latest .
docker tag  $1:latest arjoonn/$1:latest
docker push arjoonn/$1:latest
