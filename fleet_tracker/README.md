# BUS MAPS Fleet Tracker

## Run

From this directory:

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
copy .env.example .env
python bussssss.py
```

## Configuration

Set these values in `.env`:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `BUSMAPS_ADMIN_USER`
- `BUSMAPS_ADMIN_PASSWORD`

The application uses SQLite locally and Supabase for remote driver locations.

## Supabase table

Create `bus_locations` with:

- `driver` text
- `lat` numeric/double precision
- `lng` numeric/double precision
- `updated_at` timestamptz

Configure Row Level Security policies appropriate for your deployment.

## Security

Never commit the real `.env` file or database files. The source is configured to read credentials from environment variables rather than storing the Supabase key in the repository.
