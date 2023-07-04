#dev section
.PHONY: build_dev
build_dev:
	docker-compose --profile dev build

.PHONY: start_dev
start_dev:
	docker-compose --profile dev up -V

.PHONY: dump_dev_db
dump_dev_db:
	docker-compose exec -T mongo_dev sh -c 'mongodump --authenticationDatabase admin -u mongo -p mongo --db recipes_db --archive' > mongo/dump/db.dump

.PHONY: restore_dev_db
restore_dev_db:
	docker-compose exec -T mongo_dev sh -c 'mongorestore --authenticationDatabase admin -u mongo -p mongo --archive' < mongo/dump/db.dump


SERVICE_NAME := mongo_dev
CONTAINER_ID := $(shell docker-compose ps -q $(SERVICE_NAME))
CONTAINER_NAME := $(shell docker inspect --format='{{.Name}}' $(CONTAINER_ID) | sed 's/\///')
DB_DUMP_DIR := $(shell cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

.PHONY: build_mutator
build_mutator:
	docker-compose build mutator

.PHONY: start_mutator
start_mutator:
	docker-compose up mutator

.PHONY: dump_mutated_collection
dump_mutated_collection:
	docker-compose exec -T mongo_dev sh -c 'mongodump --authenticationDatabase admin -u mongo -p mongo --db recipes_db --collection=mutated --out /dump'
	docker cp $(CONTAINER_NAME):/dump/. $(DB_DUMP_DIR)/mongo/dump

.PHONY: dump_dev_collection
dump_dev_collection:
	docker-compose exec -T mongo_dev sh -c 'mongodump --authenticationDatabase admin -u mongo -p mongo --db recipes_db --collection=recipes --out /dump'
	docker cp $(CONTAINER_NAME):/dump/. $(DB_DUMP_DIR)/mongo/dump

.PHONY: restore_dev_collection
restore_dev_collection:
	docker exec $(CONTAINER_NAME) mkdir -p /dump/recipes_db
	docker cp $(DB_DUMP_DIR)/mongo/dump/recipes_db/. $(CONTAINER_NAME):/dump/recipes_db
	docker-compose exec -T mongo_dev sh -c 'mongorestore --authenticationDatabase admin -u mongo -p mongo --nsInclude=recipes_db.* /dump'

.PHONY: restore_dev_alternative
restore_dev_alternative:
	chmod a+x mongo/dump.sh
	./mongo/dump.sh

#prod section
.PHONY: build_prod
build_prod:
	docker-compose --profile prod build

.PHONY: start_prod
start_prod:
	docker-compose --profile prod up -V

.PHONY: dump_prod
dump_prod:
	docker-compose exec -T mongo_prod sh -c 'mongodump --authenticationDatabase admin -u mongo -p mongo --db recipes_db --archive' > mongo/dump/db.dump

.PHONY: restore_prod
restore_prod:
	docker-compose exec -T mongo_prod sh -c 'mongorestore --authenticationDatabase admin -u mongo -p mongo --archive' < mongo/dump/db.dump

.PHONY: idea_build
idea_build:
	docker build . -f idea/Dockerfile.idea -t recipes_idea
