.PHONY: clean
clean:
	rm -rf recipes_data/*

.PHONY: migrate
migrate:
	docker build ./mongo -f mongo/Dockerfile.migrate -t mongo_migrate
	docker run -it --network recipes mongo_migrate