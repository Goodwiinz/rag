# database/rollbacks

Rollback scripts for migrations in `../migrations/`. These files are **not**
applied automatically — they must be run manually when reverting a migration.

This directory is intentionally excluded from the Docker entrypoint mount
(which only mounts `database/migrations/`), so files here will never run
on `initdb` by accident.

## Naming

Match the prefix of the migration being rolled back:
`NNN_rollback_<original_description>.sql`

## Files

| File | Rolls back |
|---|---|
| `001_rollback_ab_testing_schema.sql` | `migrations/001_add_ab_testing_schema.sql` |
