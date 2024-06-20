#!/usr/bin/env bash

source ./.env

docker build -t krinkin/$SERVICE_NAME:$BRANCH .

