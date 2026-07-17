.PHONY: up down logs test-call pull-model models

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

pull-model:
	docker exec aibots-ollama ollama pull qwen2.5:7b-instruct

models:
	bash scripts/download-models.sh

test-call:
	bash scripts/test-call.sh

install-ubuntu:
	sudo bash scripts/install-ubuntu.sh
