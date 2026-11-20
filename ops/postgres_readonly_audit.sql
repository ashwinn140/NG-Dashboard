-- Read-only PostgreSQL cost/performance audit.
-- Run with a monitoring/read-only role. No DDL or data modifications.

-- 1) Connection states and wait events.
SELECT state, wait_event_type, wait_event, count(*) AS connections
FROM pg_stat_activity
WHERE datname = current_database()
GROUP BY state, wait_event_type, wait_event
ORDER BY connections DESC;

-- 2) Database size.
SELECT current_database() AS database_name,
       pg_size_pretty(pg_database_size(current_database())) AS database_size;

-- 3) Largest user tables (including indexes and TOAST).
SELECT schemaname, relname,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
       pg_size_pretty(pg_relation_size(relid)) AS table_size,
       pg_size_pretty(pg_indexes_size(relid)) AS indexes_size,
       n_live_tup, n_dead_tup,
       seq_scan, idx_scan
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 30;

-- 4) Largest indexes.
SELECT schemaname, tablename, indexname,
       pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
       idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 30;

-- 5) Table activity counters. Counters are cumulative since stats reset.
SELECT schemaname, relname, seq_scan, seq_tup_read,
       idx_scan, idx_tup_fetch, n_tup_ins, n_tup_upd, n_tup_del,
       n_live_tup, n_dead_tup, last_vacuum, last_autovacuum,
       last_analyze, last_autoanalyze
FROM pg_stat_user_tables
ORDER BY seq_tup_read DESC
LIMIT 30;

-- 6) Optional: top normalized statements, only if pg_stat_statements is
-- already installed and the monitoring role has permission. This query does
-- not install the extension.
SELECT queryid, calls,
       round(total_exec_time::numeric, 1) AS total_exec_ms,
       round(mean_exec_time::numeric, 1) AS mean_exec_ms,
       rows, shared_blks_hit, shared_blks_read,
       left(query, 500) AS query_sample
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 30;
