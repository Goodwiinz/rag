# database/migrations

Raw SQL migrations applied to PostgreSQL during container initialization via
`/docker-entrypoint-initdb.d`. PostgreSQL executes files in the directory
**alphabetically**, so the numeric prefix is the ordering contract.

## Convention

| Rule | Detail |
|---|---|
| Prefix format | 3-digit zero-padded integer: `001`, `002`, … `019` |
| No collisions | Every file must have a **unique** prefix — two files with the same prefix run in undefined order |
| Forward-only | Files in this directory are applied once on `initdb`; they are never rolled back automatically |
| Rollbacks | Rollback scripts live in `../rollbacks/`, never here |
| Naming | `NNN_short_description.sql` — lowercase, underscores, no spaces |

## Adding a migration

1. Find the current highest prefix: `ls database/migrations/*.sql | tail -1`
2. Add 1 to get the next prefix.
3. Name your file `NNN_describe_what_it_does.sql`.
4. Update this README's sequence table below.

## Current sequence

| # | File | What it does |
|---|---|---|
| 001 | `001_add_ab_testing_schema.sql` | A/B testing tables |
| 002 | `002_add_monitoring_schema.sql` | Monitoring / observability schema |
| 003 | `003_correct_knowledge_graph_architecture.sql` | KG schema corrections |
| 004 | `004_document_upload_schema.sql` | Documents table + processing metadata |
| 005 | `005_document_upload_simple.sql` | `document_processing_jobs` table |
| 006 | `006_knowledge_graph_analytics_dashboard.sql` | KG analytics aggregation tables |
| 007 | `007_analytics_schema.sql` | Indexes on analytics tables |
| 008 | `008_knowledge_graph_analytics_dashboard_optimized.sql` | Optimized KG analytics (partitioning, extra indexes) |
| 009 | `009_enhanced_realtime_document_processing.sql` | Real-time tracking columns on documents |
| 010 | `010_realtime_migration_strategy.sql` | Migration tracking table + backward-compat helpers |
| 011 | `011_realtime_performance_optimization.sql` | Partitioning strategy for high-volume realtime |
| 012 | `012_realtime_processing_views.sql` | Dashboard views for processing status |
| 013 | `013_websocket_realtime_updates.sql` | WebSocket integration for document processing |
| 014 | `014_realtime_status_optimizations.sql` | Additional realtime status indexes |
| 015 | `015_realtime_document_status_enhancements.sql` | Enhanced realtime status tracking columns |
| 016 | `016_realtime_document_status_fixes.sql` | Fix materialized views (correct column refs) |
| 017 | `017_realtime_document_status_final.sql` | Final materialized views with correct enum values |
| 018 | `018_realtime_system_status_fix.sql` | System status view with correct enum values |
| 019 | `019_ai_document_qa_system.sql` | AI document QA system tables |
