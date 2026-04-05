create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  created_at timestamptz not null default now()
);

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  url text not null,
  repo_url text,
  created_at timestamptz not null default now()
);

create table if not exists public.runs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  status text not null,
  live_url text,
  browser_use_model text not null default 'claude-sonnet-4.6',
  evaluation_status text not null default 'pending',
  evaluation_error text,
  custom_audience text,
  browser_use_session_id text,
  browser_use_task_id text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  error_message text,
  final_url text,
  summary text
);

alter table public.profiles enable row level security;
alter table public.projects enable row level security;
alter table public.runs enable row level security;

create policy "profiles_select_own"
on public.profiles
for select
to authenticated
using (id = auth.uid());

create policy "profiles_insert_own"
on public.profiles
for insert
to authenticated
with check (id = auth.uid());

create policy "profiles_update_own"
on public.profiles
for update
to authenticated
using (id = auth.uid())
with check (id = auth.uid());

create policy "projects_select_own"
on public.projects
for select
to authenticated
using (owner_id = auth.uid());

create policy "projects_insert_own"
on public.projects
for insert
to authenticated
with check (owner_id = auth.uid());

create policy "projects_update_own"
on public.projects
for update
to authenticated
using (owner_id = auth.uid())
with check (owner_id = auth.uid());

create policy "projects_delete_own"
on public.projects
for delete
to authenticated
using (owner_id = auth.uid());

create policy "runs_select_own"
on public.runs
for select
to authenticated
using (
  exists (
    select 1
    from public.projects
    where public.projects.id = public.runs.project_id
      and public.projects.owner_id = auth.uid()
  )
);

create policy "runs_insert_own"
on public.runs
for insert
to authenticated
with check (
  exists (
    select 1
    from public.projects
    where public.projects.id = public.runs.project_id
      and public.projects.owner_id = auth.uid()
  )
);

create policy "runs_update_own"
on public.runs
for update
to authenticated
using (
  exists (
    select 1
    from public.projects
    where public.projects.id = public.runs.project_id
      and public.projects.owner_id = auth.uid()
  )
)
with check (
  exists (
    select 1
    from public.projects
    where public.projects.id = public.runs.project_id
      and public.projects.owner_id = auth.uid()
  )
);

create policy "runs_delete_own"
on public.runs
for delete
to authenticated
using (
  exists (
    select 1
    from public.projects
    where public.projects.id = public.runs.project_id
      and public.projects.owner_id = auth.uid()
  )
);
