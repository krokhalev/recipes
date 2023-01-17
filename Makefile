.PHONY: clean
clean:
	rm -rf recipes_data/*
	rm -rf .artifacts

.PHONY: build_dev
build_dev:
	docker-compose --profile dev build

.PHONY: start_dev
start_dev:
	docker-compose --profile dev up

.PHONY: build_prod
build_prod:
	docker-compose --profile prod build

.PHONY: start_prod
start_prod:
	docker-compose --profile prod up
