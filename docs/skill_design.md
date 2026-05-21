# Project Skill Design

This file records the project-local Skill boundary for the current workflow.

## Skill 1: User Bootstrap

Purpose: initialize and maintain `user_profile/`.

Project-local Skill: `.agents/skills/user-bootstrap/SKILL.md`.

Inputs may include:

- Google Scholar profile URL.
- User-provided paper list.
- Titles and abstracts.
- Explicit research-interest notes.
- User feedback from prior recommendations.

Outputs:

- `user_profile/papers.local.jsonl`
- `user_profile/research_interests.local.md`

The bootstrap process should infer topics, methods, recurring setups, citation-check anchors, and negative preferences. Profile updates should be additive and dated unless the user explicitly requests replacement.

Only templates and examples should be committed. User-specific bootstrap outputs should use `*.local.*` filenames and remain gitignored.

## Skill 2: ArXiv Daily

Purpose: run the daily paper-reading workflow.

Project-local Skill: `.agents/skills/arxiv-daily/SKILL.md`.

Inputs:

- Date, defaulting to the current local date.
- arXiv categories, defaulting to `quant-ph`.
- Mode.
- Existing `user_profile/`.

Mode `recommend`:

- Fetch or read cached arXiv papers.
- Rank papers against user interests and prior work.
- Recommend up to 10 papers, but do not pad weak matches.
- Deep-read selected papers when needed.
- Generate research ideas only for unusually promising papers.

Mode `recommend+citation_check`:

- Run everything in `recommend`.
- Identify papers strongly related to specific user papers.
- Inspect references when possible.
- Flag likely missing citations.
- Draft factual, polite citation-request emails.

## Idea Generation Standard

Ideas should be sparse and high-value. The agent should not produce one idea per recommended paper.

Good ideas usually combine:

- a technical ingredient from the new paper,
- a concrete setup, theorem, method, or prior result from the user,
- a specific question that becomes newly feasible,
- a reason the combination is nontrivial.

Reject generic ideas such as adding noise, scaling up numerics, or applying the same method to a nearby model unless there is a precise mechanism that makes the extension scientifically meaningful.
