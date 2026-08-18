CREATE TABLE IF NOT EXISTS nutrition_targets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  target_date DATE NOT NULL DEFAULT current_date,
  calories_min INT NOT NULL,
  calories_max INT NOT NULL,
  protein_g INT NOT NULL,
  hydration_l DECIMAL NOT NULL,
  fiber_g INT NOT NULL,
  notes STRING,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, target_date)
);
