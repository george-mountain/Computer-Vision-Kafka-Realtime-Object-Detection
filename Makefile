build:
	docker compose up --build -d
up-v:
	docker compose up 
down:
	docker compose down
logs:
	docker compose logs -f
restart:
	docker compose restart
stop:
	docker compose stop
start:
	docker compose start
ps:
	docker compose ps
status:
	docker compose ps -a
api-logs:
	docker compose logs -f api

