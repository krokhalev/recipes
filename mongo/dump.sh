#!/bin/bash -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
IMAGE=mongo:5.0

docker run \
  --rm \
  --network="recipes" \
  --volume ${DIR}/dump/recipes_db/.:/data/db/dump/recipes_db \
  ${IMAGE} sh -c 'mongorestore --host mongo_dev --authenticationDatabase admin -u mongo -p mongo --nsInclude=recipes_db.* --nsFrom=recipes_db.recipes --nsTo=themenu.recipes /data/db/dump'
