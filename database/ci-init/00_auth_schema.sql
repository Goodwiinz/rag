-- CI bootstrap: pre-create the `auth` schema before GoTrue runs its migrations.
--
-- GoTrue (supabase/gotrue, GOTRUE_DB_NAMESPACE=auth) runs
-- 00_init_auth_schema.up.sql, which does `CREATE TABLE IF NOT EXISTS auth.users`
-- etc. WITHOUT a `CREATE SCHEMA auth` first. With the CI postgres using a tmpfs
-- data dir and no schema bootstrap, that migration fails with
-- `ERROR: schema "auth" does not exist (SQLSTATE 3F000)` and GoTrue never
-- becomes healthy. Creating the schema here (postgres initdb runs every file in
-- /docker-entrypoint-initdb.d on a fresh data dir) lets the migration succeed.
CREATE SCHEMA IF NOT EXISTS auth;
