# ai-crm-tracker

Two Python (FastAPI) apps in one project, run with Docker Compose:

| App | What it does | URL |
| --- | --- | --- |
| **crm** | Customers, their contact info, and quotes | http://localhost:8001/docs |
| **tracking** | Vehicles, trips to job sites, live GPS positions | http://localhost:8002/docs |
| pgAdmin | Browse the databases | http://localhost:5050 |

Both apps share one Postgres server but each has **its own database** (`crm`, `tracking`).
The tracking app stores the latest position of each vehicle in Redis.

## Run it

```bash
cp .env.example .env   # then set real passwords
docker compose up --build
```

Each app applies its database migrations on startup.

> The `crm` and `tracking` databases are created by `db/init/01-create-databases.sh`,
> which Postgres only runs when its data volume is new. If you started an older version
> of this project before, reset the volume once with `docker compose down -v`
> (this deletes the data).

## Project layout

```
docker-compose.yml
db/init/                  creates the crm and tracking databases
pgadmin/servers.json      pre-registers the Postgres server in pgAdmin
services/
  crm/
    app/                  FastAPI app (models.py, schemas.py, routers/)
    migrations/           Alembic migrations for the crm database
  tracking/
    app/                  FastAPI app (+ cache.py for Redis, crm_client.py)
    migrations/           Alembic migrations for the tracking database
```

## Data model

**crm database**

- `customers`: first name, last name, address (street, street2, city, state, postal code, country)
- `customer_contacts`: phone / email / other per customer, with a label (e.g. "mobile") and
  an `is_primary` flag; at most one primary per kind per customer
- `quotes`: customer, title, status (`draft`, `sent`, `accepted`, `declined`, `expired`),
  job site address (defaults to the customer's address), valid-until date, notes
- `quote_line_items`: description, quantity, unit price; the API returns each line total
  and the quote total

**tracking database**

- `vehicles`: name, license plate (unique), active flag
- `trips`: a vehicle's drive to the job site of a CRM quote. Stores the CRM `quote_id` and
  `customer_id` and a copy of the job site address taken from the quote when the trip is
  created. Status: `planned` → `en_route` → `arrived` (or `cancelled`). A vehicle can only
  be en route on one trip at a time.
- `location_pings`: latitude, longitude, speed, heading and device time. Pings are linked
  to the vehicle's en-route trip automatically.

The two databases are not linked by foreign keys. The tracking app calls the CRM API to
look up a quote when a trip is created, and only **accepted** quotes can get a trip.

## Example: from customer to vehicle on its way

```bash
# 1. Customer with contact info
curl -X POST localhost:8001/customers -H 'content-type: application/json' -d '{
  "first_name": "Ada", "last_name": "Lovelace",
  "street": "1 Main St", "city": "Boston", "state": "MA", "postal_code": "02101",
  "contacts": [{"kind": "phone", "value": "555-0100", "label": "mobile", "is_primary": true}]
}'

# 2. Quote with line items (job site = customer address unless site_* fields are given)
curl -X POST localhost:8001/quotes -H 'content-type: application/json' -d '{
  "customer_id": 1, "title": "Roof repair",
  "line_items": [{"description": "Shingles", "quantity": "10", "unit_price": "45.50"}]
}'

# 3. Customer accepts
curl -X PATCH localhost:8001/quotes/1 -H 'content-type: application/json' -d '{"status": "accepted"}'

# 4. Vehicle and trip to the job site
curl -X POST localhost:8002/vehicles -H 'content-type: application/json' -d '{"name": "Truck 1", "license_plate": "ABC123"}'
curl -X POST localhost:8002/trips -H 'content-type: application/json' -d '{"vehicle_id": 1, "quote_id": 1}'
curl -X POST localhost:8002/trips/1/start

# 5. The vehicle's GPS device / phone reports positions
curl -X POST localhost:8002/vehicles/1/locations -H 'content-type: application/json' \
  -d '{"latitude": 42.36, "longitude": -71.06, "speed_kph": 48, "recorded_at": "2026-11-10T15:04:05Z"}'

# 6. Where is it now? Where has it been?
curl localhost:8002/vehicles/1/location
curl localhost:8002/trips/1/route

# 7. Arrived at the job site
curl -X POST localhost:8002/trips/1/arrive
```

See `/docs` on each app for every endpoint.

## Changing the database schema

Edit `app/models.py` in the app, then generate and review a migration:

```bash
docker compose exec crm alembic revision --autogenerate -m "describe the change"
```

The file is written inside the container. To keep it, either run Alembic locally with
`DATABASE_URL` pointing at Postgres (uncomment the `5432` port mapping), or copy it out
with `docker compose cp`. It is applied on the next start, or right away with
`docker compose exec crm alembic upgrade head`. Use `tracking` instead of `crm` for the
other app.

## pgAdmin

Open http://localhost:5050. pgAdmin's own login is turned off (desktop mode), so only
expose port 5050 on a trusted machine. The "ai-crm-tracker" server is already listed;
enter `POSTGRES_PASSWORD` when asked. If you change `POSTGRES_USER`, update
`pgadmin/servers.json` to match.

## Stop

```bash
docker compose down        # keep data
docker compose down -v     # also delete all data
```
