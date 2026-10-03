COMPOSE := docker compose

.PHONY: up down logs psql

up:
	$(COMPOSE) up -d postgres

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f postgres

psql:
	$(COMPOSE) exec postgres psql -U redtraces -d redtracesai
