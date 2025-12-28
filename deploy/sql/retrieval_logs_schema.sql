-- 检索审计日志 — Agent pipeline 写入，供反馈/Grafana 关联

CREATE TABLE IF NOT EXISTS retrieval_logs (
    log_id UUID PRIMARY KEY,
    session_id TEXT,
    query TEXT NOT NULL,
    search_query TEXT,
    hit_count INT NOT NULL DEFAULT 0,
    top_source_file TEXT,
    refused BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_retrieval_logs_session ON retrieval_logs (session_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_logs_created ON retrieval_logs (created_at DESC);
