-- Production partitioning for the high-volume append-only log tables.
-- The base tables are created by SQLAlchemy/Alembic; in production you should
-- instead create them PARTITION BY RANGE (ts) using this template, then let the
-- Celery 'ensure_log_partitions' task pre-create upcoming monthly partitions.
--
-- Apply this AFTER the base schema, OR adapt the model DDL to declare partitioning.
-- Example shown for checkin_event; repeat the pattern for provisioning_log,
-- firmware_log, and error_log.

-- 1. Recreate as partitioned (do this on a fresh DB, or migrate data first):
--
-- DROP TABLE IF EXISTS checkin_event;
-- CREATE TABLE checkin_event (
--     id          BIGINT GENERATED ALWAYS AS IDENTITY,
--     device_id   BIGINT,
--     mac         CHAR(12) NOT NULL,
--     ip          VARCHAR(45),
--     ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
--     user_agent  VARCHAR(255),
--     config_hash VARCHAR(64),
--     PRIMARY KEY (id, ts)
-- ) PARTITION BY RANGE (ts);
--
-- CREATE INDEX ix_checkin_mac      ON checkin_event (mac);
-- CREATE INDEX ix_checkin_ts       ON checkin_event (ts);
-- CREATE INDEX ix_checkin_dev_ts   ON checkin_event (device_id, ts);

-- 2. Create the current + next monthly partitions (the beat task automates this):
--
-- CREATE TABLE checkin_event_2026_06 PARTITION OF checkin_event
--     FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
-- CREATE TABLE checkin_event_2026_07 PARTITION OF checkin_event
--     FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

-- 3. Retention: dropping an old partition is an O(1) metadata operation:
--
-- DROP TABLE checkin_event_2026_01;   -- prune Jan once past retention

-- Function the Celery task calls to create next month's partition for any table:
CREATE OR REPLACE FUNCTION ensure_monthly_partition(
    base_table text,
    month_start date
) RETURNS void AS $$
DECLARE
    part_name text := base_table || '_' || to_char(month_start, 'YYYY_MM');
    next_start date := (month_start + interval '1 month')::date;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = part_name) THEN
        EXECUTE format(
            'CREATE TABLE %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
            part_name, base_table, month_start, next_start
        );
    END IF;
END;
$$ LANGUAGE plpgsql;
