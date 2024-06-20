#!/usr/bin/env bash

BRANCH=`git rev-parse --abbrev-ref HEAD`

REPO=`git rev-parse --show-toplevel`

SERVICE_NAME=`basename $REPO`
CONTAINER_NAME=$SERVICE_NAME

T=`date +%Y-%m-%d-%H-%M-%S`
mv ./deploy/.env ./deploy/.env.$T

VERSION_FILE=./VERSION

echo "BRANCH=$BRANCH" > ./.env
echo "REPO=$REPO" >> ./.env
echo "SERVICE_NAME=$SERVICE_NAME" >> ./.env
echo "CONTAINER_NAME=$CONTAINER_NAME"  >> ./.env
echo "CONTAINER_DATA=./.data/"  >> ./.env
echo "VERSION_FILE=$VERSION_FILE"  >> ./.env

echo "Version: $BRANCH `hostname` `date`" > $VERSION_FILE

cat ./.env
mkdir -p ./.data/
cp ./deploy/docker-compose.yml ./docker-compose.yml
sed "s/^#UNCOMMENT_ME_FOR_DEV//" ./deploy/docker-compose.yml > ./docker-compose.yml

