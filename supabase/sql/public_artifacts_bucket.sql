insert into storage.buckets (id, name, public)
values ('uxray-artifacts', 'uxray-artifacts', true)
on conflict (id) do update
set public = excluded.public;

drop policy if exists "public read uxray artifacts" on storage.objects;

create policy "public read uxray artifacts"
on storage.objects
for select
to public
using (bucket_id = 'uxray-artifacts');
