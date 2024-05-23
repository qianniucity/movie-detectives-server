all:
	@echo "see README.md"

.venv:
	poetry install

.PHONY: run
run:
	uvicorn api.main:app --reload

.PHONY: test
test:
	python -m unittest -v

.PHONY: ruff
ruff:
	ruff check --fix

.PHONY: clean
clean:
	rm -rf movie-detectives-server_latest.tar.gz

.PHONY: build
build: clean
	docker image rm movie-detectives-server
	docker build -t movie-detectives-server .
	docker save movie-detectives-server:latest | gzip > movie-detectives-server_latest.tar.gz
