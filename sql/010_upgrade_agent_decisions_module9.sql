ALTER TABLE agent_decisions
  ADD COLUMN IF NOT EXISTS idempotency_key STRING;

ALTER TABLE agent_decisions
  ADD COLUMN IF NOT EXISTS parent_decision_id UUID;

UPDATE agent_decisions
SET idempotency_key = concat('legacy:', id::STRING)
WHERE idempotency_key IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS agent_decisions_user_type_key_idx
ON agent_decisions (user_id, decision_type, idempotency_key);
