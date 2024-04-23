#!/bin/bash

set -e

host="$1"
shift
cmd="$@"

until nc -z -v -w100 $host 9092; do
  echo "Waiting for Kafka to start..."
  sleep 1
done

>&2 echo "Kafka is up - executing command"
exec $cmd