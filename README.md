# Python + PostgreSQL + Redis (Docker Compose)

```bash
cp .env.example .env   # then change the password
docker compose up --build
```

Check it works:

```bash
curl localhost:8000/health   # {"postgres":"ok","redis":"ok"}
curl localhost:8000/hits     # counter stored in Redis
```

## pgAdmin

Open http://localhost:5050 and log in with `PGADMIN_DEFAULT_EMAIL` / `PGADMIN_DEFAULT_PASSWORD` from `.env`.
The "app db" server is already listed; enter `POSTGRES_PASSWORD` when it asks.
If you change `POSTGRES_USER` or `POSTGRES_DB`, update `pgadmin/servers.json` to match.

Stop with `docker compose down` (add `-v` to also delete the data volumes).

If you change `POSTGRES_PASSWORD`, update `DATABASE_URL` to match.
