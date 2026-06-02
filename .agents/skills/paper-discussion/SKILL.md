---
name: paper-discussion
description: "Use when the user asks substantive follow-up questions about a specific paper or asks to discuss, explain, critique, or connect a paper to their research. Maintain one evolving local note per paper in data/notes/ARXIV_ID.md, read local notes and source before analysis, and integrate feedback-memory during sustained discussion."
---

# Paper Discussion

Use this skill for sustained or explicit discussion of one paper. Do not use it for ordinary daily ranking unless the conversation shifts into discussing a specific paper.

## Trigger Rules

Use this skill when:

- The user asks a substantive question about a specific arXiv paper.
- The user asks to explain, discuss, critique, interpret, or connect a paper to their work.
- The user continues asking follow-up questions about the same paper.
- A `data/notes/ARXIV_ID.md` note exists and the user asks about that paper.

Do not create a note for feedback-only turns. If the user only gives feedback such as `+1`, `interesting`, `not useful`, or a reusable preference signal, invoke `feedback-memory`; update the paper note only if it already exists.

## Local Order Of Operations

For substantive paper discussion:

1. Resolve the arXiv ID.
2. Read `data/notes/ARXIV_ID.md` first if it exists.
3. Locate local metadata/reports to identify title, source date, and prior recommendation context.
4. Check for existing local paper material under `data/raw/arxiv/*/sources/ARXIV_ID/`.
5. If local source/PDF/text is missing, run:

```bash
.conda/arxiv-daily/bin/arxiv-daily download ARXIV_ID
```

6. Re-check the local source folder.
7. If no local paper artifact can be obtained, report that grounded discussion is blocked and avoid deep analysis from memory or abstract-only context.

Use local source as the source of truth. Use network only for missing source acquisition, resolving absent metadata, or version/publication checks explicitly requested by the user.

## Source Reading

Prefer targeted local inspection:

- Existing note first.
- Abstract, introduction, result/theorem statements, method sections, discussion, limitations.
- `.bbl` / `.bib` only if needed for context.

Do not read whole large TeX trees unless necessary. Use `rg` and snippets.

## Paper Notes

Maintain one evolving note per paper:

```text
data/notes/ARXIV_ID.md
```

The note should be compact but self-contained. Use flexible sections appropriate to the paper, for example:

- Core Idea
- Setup
- Main Result
- Mechanism
- Technical Stack
- Weaknesses And Caveats
- Takeaway
- Promising Future Ideas

Always keep this section last:

```md
## Discussion Log And User Interest
```

Update policy:

- Create the note on the first substantive paper question.
- Revise synthesis sections as understanding improves.
- Do not preserve outdated interpretations except by correcting them.
- Keep `Discussion Log And User Interest` append-only, except typo fixes.
- Add concise log bullets for every substantive discussion turn.
- Do not add citation-alert sections or email drafts to paper notes.
- Add future ideas only when they naturally emerge or the user asks for them.

## Chat Style

Answer the user's current question directly. Do not force a fixed template in chat. Use the note for continuity, not for verbose terminal output.

Distinguish clearly between:

- What the paper proves or demonstrates.
- What the paper suggests.
- Your inference or interpretation.
- Why it matters for the user's research.

## Feedback Integration

At the end of each substantive paper-discussion turn, run the `feedback-memory` checklist.

Write feedback when:

- The user gives explicit `+1`, `+2`, `-1`, `-2`, or evaluative language.
- The user asks several substantive follow-up questions about the same paper.
- The user connects the paper to their research interests.
- The user asks for concrete future ideas or actionability.

Scoring convention:

- `score: 1`: Several substantive follow-ups or mild positive interest.
- `score: 2`: Explicit strong praise, high priority, or strong reusable preference.
- `score: -1`: Skeptical or weak negative judgment.
- `score: -2`: User concludes the paper is trivial, cheating, wrong, not useful, or should be avoided.

Several rounds of substantive discussion count as weak positive interest by default unless the user shows an obvious negative attitude. Purely logistical questions do not count.

Use `feedback-memory` for durable idea records. Paper notes may contain lightweight possible ideas, but `user_profile/ideas.local.jsonl` should only be created or updated through the feedback-memory workflow.
