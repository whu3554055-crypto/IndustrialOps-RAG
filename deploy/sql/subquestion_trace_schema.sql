-- SubQuestion 检索轨迹 — retrieval_logs 可选 JSON 列

ALTER TABLE retrieval_logs
  ADD COLUMN IF NOT EXISTS sub_question_trace JSONB;
