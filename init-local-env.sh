#!/usr/bin/env bash

BRANCH=`git rev-parse --abbrev-ref HEAD`

REPO=`git rev-parse --show-toplevel`

SHA_FULL=`git rev-parse HEAD`

COMMIT_TIME=$(git show -s --format=%ci "$SHA_FULL")

remote_url=$(git remote get-url origin)

# Check if the remote URL was fetched successfully
if [ -z "$remote_url" ]; then
  echo "Failed to retrieve git URL"
  exit 1
fi

# Extract the organization or account name based on the URL format
if [[ $remote_url == https://github.com/* ]]; then
  ORG_NAME=$(echo $remote_url | sed -E 's|https://github.com/([^/]+)/.*|\1|')
elif [[ $remote_url == git@github.com:* ]]; then
  ORG_NAME=$(echo $remote_url | sed -E 's|git@github.com:([^/]+)/.*|\1|')
else
  echo "URL format not recognized."
  exit 1
fi

ORG_NAME=$(echo "$ORG_NAME" | tr '[:upper:]' '[:lower:]')

SERVICE_NAME=`basename $REPO`
CONTAINER_NAME=$SERVICE_NAME

T=`date +%Y-%m-%d-%H-%M-%S`
mv ./deploy/.env ./deploy/.env.$T

VERSION_FILE=./VERSION

echo "PROJECT=$ORG_NAME" > ./.env
echo "REPO=$REPO" >> ./.env
echo "BRANCH=$BRANCH" >> ./.env
echo "SHA_FULL=$SHA_FULL" >> ./.env
echo "COMMIT_TIME=$COMMIT_TIME" >> ./.env
echo "SERVICE_NAME=$SERVICE_NAME" >> ./.env
echo "CONTAINER_NAME=$CONTAINER_NAME"  >> ./.env
echo "CONTAINER_DATA=./.data/"  >> ./.env
echo "VERSION_FILE=$VERSION_FILE"  >> ./.env
# echo "DEPLOY_TIME=$(date +"%Y-%m-%d %H:%M:%S %z")" >> ./.env # UNCOMMENT TO TEST DEPLOY TIME AND SERVICE UP TIME FOR /version
echo "Version: $BRANCH `hostname` `date`" > $VERSION_FILE

#neo4j-configurations
#echo "NEO4J_URI=bolt://neo4j-db:7687" >> ./.env
#echo "NEO4J_USER=neo4j" >> ./.env
#echo "NEO4J_PASSWORD=secret" >> ./.env
#echo "NEO4J_AUTH=neo4j/secret" >> ./.env

echo "MEMGRAPH_HOST=memgraph" >> ./.env
echo "MEMGRAPH_PORT=7687" >> ./.env

read -p "Enter OPENAI_API_KEY: " OPENAI_API_KEY
echo "OPENAI_API_KEY=$OPENAI_API_KEY" >> ./.env

cat ./.env
mkdir -p ./.data/
cp ./deploy/docker-compose.yml ./docker-compose.yml

