CREATE TABLE IF NOT EXISTS daily_checkins (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  checkin_date DATE NOT NULL DEFAULT current_date,
  sleep_hours DECIMAL,
  stress_level INT,
  energy_level INT,
  soreness_level INT,
  sore_muscle_groups STRING[],
  pain_notes STRING,
  weight_kg DECIMAL,
  workout_completed STRING,
  nutrition_adherence STRING,
  free_text_note STRING,
  checkin_details JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS daily_checkins_user_date_idx
ON daily_checkins (user_id, checkin_date DESC, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS daily_checkins_user_date_unique_idx
ON daily_checkins (user_id, checkin_date);
