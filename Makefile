.PHONY: clean
clean:
	rm -rf .artifacts

#dev section
.PHONY: build_dev
build_dev:
	docker-compose --profile dev build

.PHONY: start_dev
start_dev:
	docker-compose --profile dev up -V

.PHONY: dump_dev
dump_dev:
	docker-compose exec -T mongo_dev sh -c 'mongodump --authenticationDatabase admin -u mongo -p mongo --db recipes_db --archive' > mongo/dump/db.dump

.PHONY: restore_dev
restore_dev:
	docker-compose exec -T mongo_dev sh -c 'mongorestore --authenticationDatabase admin -u mongo -p mongo --archive' < mongo/dump/db.dump

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
