ALTER TABLE workout_plans
ADD COLUMN IF NOT EXISTS validation_status STRING NOT NULL DEFAULT 'pending';

ALTER TABLE workout_plans
ADD COLUMN IF NOT EXISTS validation_notes JSONB;

ALTER TABLE workout_plans
ADD COLUMN IF NOT EXISTS retrieved_memory_ids UUID[];

ALTER TABLE workout_plans
ADD COLUMN IF NOT EXISTS generation_attempt INT NOT NULL DEFAULT 1;
