## Inspiration
got inspired that i saw the fitness workout suggestions all over social medias like ig, but its a burden to integrate all the videos i saw and make it into a good workout plan. hence I decided to do one myself, provided the users basic info and his/her goal, to built a personalised full workout plan instead of a generic one.

## What it does
1. firstly, it register the user. if user exist, we would continue to our basic daily checkins/updates
2. users input their basic info, eg: - Age
- Height
- Starting weight
- Training experience
- Equipment access
- Weekly availability
- Injury or medical constraints
- Diet preferences or restrictions
- Current activity level
3. Users provide their goal accordingly, eg weight loss, keep lean. then agent could plan (will provide context for agent instead of generating randomly)
4. daily checkins, users update their daily status, like sleep duration, stress level, sore muscle groups, etc
5. apply math formula to calcuate the score of users by theri daily status
6. could adjust the plan according to the users readiness day by day, instead of just following the rigid workout plan
7. provide nutrition target using simple calculations

## How we built it

We built the memory layer around four distinct stores instead of one blob: a **static profile**
table for stable facts (goals, injuries, equipment), an **adaptive daily** table for check-ins
(sleep, soreness, stress), a **decision log** that records every plan change the agent makes and
why, and a **vector memory** table (CockroachDB VECTOR + Ollama embeddings) for semantic recall
of similar past situations.

The core pipeline follows a retrieve → generate → validate → regenerate loop:

1. Each day's check-in is parsed into structured fields via Ollama, then run through a
   personalized readiness score (per-user z-scores over sleep/stress/energy/soreness, scored
   through a sigmoid penalty curve rather than hard thresholds).
2. Before generating or repairing a plan, we query vector memory for similar past situations for
   that user (e.g. "low sleep + high soreness") and inject the retrieved precedent directly into
   the generation prompt, so past outcomes actually influence today's plan.
3. Ollama generates the plan/repair, but nothing ships un-checked — a deterministic validator
   layer enforces equipment access, injury exclusions, and volume limits, and pain/safety flags
   act as a hard ceiling on the readiness score rather than just another subtracted point.
4. Every decision — the score, the retrieved memories used, the validation result — is written
   to an audit table, so the agent can explain *why* a plan changed, not just report that it did.

Deterministic logic handles anything safety- or math-critical (identity matching, the readiness
formula, validation rules); the LLM is scoped to natural-language parsing and creative plan
generation within those guardrails.

## Challenges we ran into

- **Deciding what should be deterministic vs. LLM-driven.** Our first instinct was to let the
  model handle most of the pipeline, but anything safety-critical — the readiness score, pain
  gating, user identity matching — needed to be reproducible and explainable on demand, so we
  drew a hard line: LLMs interpret unstructured input, code makes decisions.
- **Making vector retrieval actually matter.** It's easy to add a vector table that never
  meaningfully changes an output. We had to explicitly wire retrieved memories into the
  generation prompt and log which memory IDs were used, so retrieval is provably load-bearing
  rather than decorative.
- **Avoiding false precision in the readiness score.** An early version used hard point
  deductions (e.g. "-20 if sleep < 6h"), which produced arbitrary cliffs at the threshold. We
  moved to continuous, personalized z-score + sigmoid penalties instead.
- **Keeping the LLM inside guardrails.** Local models (Ollama) are more prone to malformed or
  constraint-violating output than hosted APIs, so every generation goes through a deterministic
  validator with a bounded retry budget before anything is stored or shown to the user.

## Accomplishments that we're proud of
1. about the plan repair, we used a hybrid version, instead of solely depending on hardcoded rules, we integrate both llm and prewritten rules together, fallback once llm gets it wrong
## What we learned

## What's next for Untitled

## Architecture
User Input
  → Agent Orchestration Layer (run_module.py)
  → Module Services (m1-m8)
  → CockroachDB Repositories (9 tables)
  → Ollama (chat + embeddings)
  → Vector Retrieval (cosine similarity via CockroachDB VECTOR index)
  → Deterministic Validators (Python guardrails)

LLMs interpret unstructured input; code makes decisions. Safety, math, validation, and identity matching are all deterministic Python. Ollama handles natural-language parsing and creative plan generation within those guardrails.