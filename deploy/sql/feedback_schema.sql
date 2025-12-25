-- M7 用户反馈表 — 与 apps/feedback.py 对齐
-- 执行：python scripts/init_feedback_db.py

CREATE TABLE IF NOT EXISTS feedback_events (
    event_id UUID PRIMARY KEY,
    session_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    rating SMALLINT NOT NULL CHECK (rating BETWEEN -1 AND 1),
    comment TEXT,
    query_text TEXT,
    answer_preview TEXT,
    retrieval_log_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_session ON feedback_events (session_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback_events (rating);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback_events (created_at DESC);
