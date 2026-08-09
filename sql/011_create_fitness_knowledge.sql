CREATE TABLE IF NOT EXISTS fitness_knowledge (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic STRING NOT NULL UNIQUE,
  content STRING NOT NULL,
  source_name STRING,
  source_url STRING,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
