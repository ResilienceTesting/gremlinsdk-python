#!/bin/bash

#gunicorn -D -w 1 -b 0.0.0.0:10081 --reload details:app
#gunicorn -D -w 1 -b 0.0.0.0:10082 --reload reviews:app
#gunicorn -w 1 -b 0.0.0.0:19080 --reload --access-logfile prod.log --error-logfile prod.log productpage:app >>prod.log 2>&1 &

set -o errexit
##build the gremlinproxy
docker run -v "$PWD":"/go/bin" -it golang:1.6 go get -u github.com/ResilienceTesting/gremlinproxy
cp gremlinproxy gateway/
cp gremlinproxy productpage/
rm gremlinproxy
pushd productpage
  docker build -t productpage .
popd

pushd details
  docker build -t details .
popd

pushd reviews
  docker build -t reviews .
popd

pushd gateway
  docker build -t gateway .
popd

