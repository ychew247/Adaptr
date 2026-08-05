CREATE TABLE IF NOT EXISTS workout_plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  goal_id UUID REFERENCES goals(id),
  week_start DATE NOT NULL,
  exercise_names STRING[],
  target_muscle_groups STRING[],
  intensity_band STRING,
  plan_json JSONB NOT NULL,
  status STRING NOT NULL DEFAULT 'active',
  validation_status STRING NOT NULL DEFAULT 'pending',
  validation_notes JSONB,
  retrieved_memory_ids UUID[],
  generation_attempt INT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS workout_plans_user_status_idx
ON workout_plans (user_id, status, created_at DESC);
