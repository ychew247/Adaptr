CREATE TABLE IF NOT EXISTS user_profiles (
  user_id UUID PRIMARY KEY REFERENCES users(id),
  age INT,
  height_cm DECIMAL,
  starting_weight_kg DECIMAL,
  training_experience STRING,
  equipment_access STRING[],
  weekly_availability STRING,
  injury_notes STRING,
  medical_constraints STRING,
  diet_preferences STRING,
  activity_level STRING,
  bmr_formula_profile STRING,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
