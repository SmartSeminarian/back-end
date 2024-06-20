#!/usr/bin/env bash

source ./.env

docker build -t krinkin/$PROJECT.$SERVICE_NAME:$BRANCH .

