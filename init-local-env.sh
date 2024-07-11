#!/usr/bin/env bash

BRANCH=`git rev-parse --abbrev-ref HEAD`

REPO=`git rev-parse --show-toplevel`

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
echo "SERVICE_NAME=$SERVICE_NAME" >> ./.env
echo "CONTAINER_NAME=$CONTAINER_NAME"  >> ./.env
echo "CONTAINER_DATA=./.data/"  >> ./.env
echo "VERSION_FILE=$VERSION_FILE"  >> ./.env
echo "Version: $BRANCH `hostname` `date`" > $VERSION_FILE

cat ./.env
mkdir -p ./.data/
cp ./deploy/docker-compose.yml ./docker-compose.yml
sed -i "s/^#UNCOMMENT_ME_FOR_DEV//" ./docker-compose.yml
sed -i '0,/5000/s/5000/5000:5000/' ./docker-compose.yml
sed -i "s/^            test: curl --fail http:\/\/api-stage.csai.site\/version || exit 1//" ./docker-compose.yml
sed -i "s/^        image: krinkin\/\$PROJECT\.\$SERVICE_NAME:\$BRANCH//" ./docker-compose.yml
sed -i "/#DELETE_BLOCK_FOR_DEV/,/#DELETE_BLOCK_FOR_DEV/d" ./docker-compose.yml

