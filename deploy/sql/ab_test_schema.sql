-- Phase 3 A/B 分配记录 — 与 apps/ab_test/assignment_log.py 对齐
-- 执行：python scripts/init_db.py（需 persistence 使用 postgresql）

CREATE TABLE IF NOT EXISTS ab_assignments (
    log_id UUID PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    variant CHAR(1) NOT NULL CHECK (variant IN ('A', 'B')),
    retrieval_mode TEXT NOT NULL,
    scope TEXT NOT NULL,
    latency_ms REAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ab_assign_experiment ON ab_assignments (experiment_id);
CREATE INDEX IF NOT EXISTS idx_ab_assign_variant ON ab_assignments (experiment_id, variant);

-- 检索日志关联实验（可选列，向后兼容）
ALTER TABLE retrieval_logs
  ADD COLUMN IF NOT EXISTS experiment_id TEXT,
  ADD COLUMN IF NOT EXISTS variant CHAR(1),
  ADD COLUMN IF NOT EXISTS retrieval_mode TEXT;
