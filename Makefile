COMPOSE = docker compose -f infra/docker-compose.yml --env-file infra/.env
.PHONY: up down logs build ingest eval test validate-rules psql web-up
build:          ; $(COMPOSE) build
up:             ; $(COMPOSE) up -d db api
web-up:         ; $(COMPOSE) --profile web up -d --build
down:           ; $(COMPOSE) --profile web down
logs:           ; $(COMPOSE) logs -f api
ingest:         ; $(COMPOSE) run --rm api ingest
eval:           ; $(COMPOSE) run --rm api eval
test:           ; $(COMPOSE) run --rm -e NIYAM_DATABASE_URL=postgresql+psycopg://niyam:$$(grep ^POSTGRES_PASSWORD infra/.env | cut -d= -f2)@db:5432/niyam api test
validate-rules: ; python3 -I rules/validate.py
psql:           ; $(COMPOSE) exec db psql -U niyam -d niyam
