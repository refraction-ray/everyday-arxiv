---
name: feedback-memory
description: "Maintain private paper and idea feedback memory for this project: record sparse user feedback, update idea status, and promote only stable feedback patterns into the durable research profile."
---

# Feedback Memory

Use this skill when the user gives feedback on a recommended arXiv paper, a close-reading result, a citation-check judgment, or a research idea, or when they ask to update preferences from prior feedback.

This skill is separate from `arxiv-daily`: daily screening finds candidates; feedback-memory maintains the user's evolving taste.

## Files

- Raw feedback log: `user_profile/feedback.local.jsonl` private, gitignored.
- Feedback schema example: `user_profile/feedback.example.jsonl` public.
- Idea log: `user_profile/ideas.local.jsonl` private, gitignored.
- Idea schema example: `user_profile/ideas.example.jsonl` public.
- Durable profile: `user_profile/research_interests.local.md` private, gitignored.

If a private file is missing, create it only when needed. Do not write user-specific feedback into public template/example files.

## Scoring

Keep feedback simple but allow intensity:

- `score: 2` means strongly positive; the user clearly values this paper or idea.
- `score: 1` means mildly positive/useful.
- `score: 0` means neutral, unclear, or informational.
- `score: -1` means mildly negative/not useful.
- `score: -2` means strongly negative; the user clearly rejects this paper, idea, or style.

Use an optional `reason` string when the user gives one. If the user only says "good", "useful", "not relevant", or similar, record the score and leave `reason` empty or very short.

Do not invent feedback from ordinary follow-up questions. Only record feedback when the user evaluates a paper, recommendation, idea, or preference.

## Feedback Records

Append one JSON object per feedback event to `user_profile/feedback.local.jsonl`.

Paper feedback:

```json
{"schema_version":1,"created_at":"YYYY-MM-DDTHH:MM:SS+08:00","kind":"paper","arxiv_id":"2605.00001","score":2,"reason":"Highly relevant to my current tensor-network direction."}
```

Idea feedback:

```json
{"schema_version":1,"created_at":"YYYY-MM-DDTHH:MM:SS+08:00","kind":"idea","idea_id":"2026-05-21-2605-00001-short-slug","score":-2,"reason":"Too generic; just swapping the physical system is not interesting."}
```

Only include extra fields when they are directly useful for disambiguation, such as `title`, `source_arxiv_ids`, or `context_date`.

## Idea Updates

When feedback targets an idea, update the matching record in `user_profile/ideas.local.jsonl` if it exists.

During discussion of an existing idea, also refine the idea record when the user clarifies the scientific question, diagnostic, model, observable, implementation route, novelty, or provenance. Do this even when the user is not giving positive or negative evaluative feedback. In that case, update fields such as `summary`, `novelty_reason`, `actionability`, `notes`, or a concise `feedback` note, but do not append a scored feedback record unless the user actually evaluates the idea.

Preserve the original source and intent while refining. Prefer additive or clarifying edits over replacing the idea wholesale; keep enough provenance in `notes` to recover why the idea was generated and which discussion refined it.

Maintain these fields when possible:

- `feedback_score`: cumulative integer score for that idea.
- `feedback`: short latest or summarized feedback note.
- `status`: `proposed`, `promising`, `rejected`, `in_progress`, or `done`.

Status rules:

- If the user explicitly rejects an idea, gives `score: -2`, or cumulative `feedback_score <= -2`, set `status` to `rejected`.
- If the user gives `score: 2` or cumulative `feedback_score >= 2`, set `status` to `promising`.
- If the user says they want to work on it, set `status` to `in_progress`.
- If the user says it was completed, set `status` to `done`.

Do not delete rejected ideas. Keeping them helps avoid regenerating the same weak idea later.

## Profile Promotion

Single feedback entries are evidence, not durable profile changes.

After appending feedback, inspect recent feedback only enough to decide whether a stable pattern exists. Promote feedback into `user_profile/research_interests.local.md` only when at least one condition holds:

- The user explicitly says to remember, update the profile, or treat the preference as stable.
- At least two weak feedback records have the same direction and a similar reason, topic, method, setup, or style.
- Cumulative feedback for a clearly identifiable theme reaches `>= 2` or `<= -2`.
- A single `score: 2` or `score: -2` entry has a clear reason that identifies a reusable preference.
- A single negative item is exceptionally explicit, for example "I never want this kind of idea again."

When promoting, add a dated note under the most appropriate profile section, usually `Active Interests`, `Methods And Skills`, `Negative Preferences`, or `Feedback Log`.

Preserve old profile content unless the user explicitly supersedes it. Prefer additive dated notes such as:

```text
- 2026-05-21: Feedback on multiple recommendations suggests stronger interest in X when it connects to Y, and lower interest in generic Z extensions.
```

Do not overfit durable preferences to one paper.

## Before Future Recommendations

When running recommendations, use `research_interests.local.md` as the durable source of preference and consult `feedback.local.jsonl` for recent evidence that may not yet be promoted.

Recent negative feedback can downrank similar papers or ideas even before it becomes a permanent profile rule, but explain this only when it affects a recommendation.
