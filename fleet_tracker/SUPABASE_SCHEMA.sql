create table if not exists public.bus_locations (
  driver text primary key,
  lat double precision not null,
  lng double precision not null,
  updated_at timestamptz not null default now()
);

create index if not exists bus_locations_updated_at_idx
  on public.bus_locations (updated_at desc);

-- Review and configure Row Level Security policies for your deployment.
-- Do not blindly expose write access to anonymous clients in production.
