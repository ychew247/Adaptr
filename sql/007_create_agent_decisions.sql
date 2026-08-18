CREATE TABLE IF NOT EXISTS agent_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  checkin_id UUID REFERENCES daily_checkins(id),
  plan_id UUID REFERENCES workout_plans(id),
  trigger_date DATE NOT NULL,
  decision_type STRING NOT NULL,
  reason STRING NOT NULL,
  data_used JSONB NOT NULL DEFAULT '{}',
  plan_change JSONB NOT NULL DEFAULT '{}',
  safety_flags STRING[],
  validation_status STRING NOT NULL DEFAULT 'pending',
  validation_notes JSONB,
  retrieved_memory_ids UUID[],
  generation_attempt INT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT agent_decisions_repair_idempotency
    UNIQUE (user_id, plan_id, trigger_date, decision_type)
);

CREATE INDEX IF NOT EXISTS agent_decisions_user_created_idx
ON agent_decisions (user_id, created_at DESC);
