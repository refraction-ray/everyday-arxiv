---
name: arxiv-daily
description: "Run the daily arXiv workflow for this project: fetch a date/category batch, recommend papers against the local user profile, perform selective close reading, check missing citations, and write user-facing reports with citation-email drafts."
---

# arXiv Daily

Use this skill when the user asks to run daily arXiv recommendations, close reading, idea generation, or citation checks.

## Inputs

- Date, defaulting to the current local date.
- arXiv categories, defaulting to `quant-ph`.
- Mode: `recommend` or `recommend+citation_check`.
- Local profile files:
  - `user_profile/research_interests.local.md`
  - `user_profile/papers.local.jsonl`

## Fetching

Use the project CLI:

```bash
.conda/arxiv-daily/bin/arxiv-daily fetch --date YYYY-MM-DD --category quant-ph
```

If the requested local date returns zero papers, check adjacent submitted dates and use the latest non-empty batch. Always make the date convention explicit.

Report and cache folder names must use the arXiv source/fetch date, not the agent run date. For example, if the run date is `YYYY-MM-DD` but the latest non-empty arXiv batch is `submittedDate=YYYY-MM-DD-1`, write reports under `data/reports/<source-date>/`.

## Recommendation

Read the local profile before ranking. Rank by concrete relevance, not by broad keyword matches.

Use the local profile as the source of topic-specific preferences, including active topics, lower-priority topics, method preferences, citation anchors, and negative preferences. Do not encode a single user's current topics directly in this skill.

When the profile contains topic-specific weighting rules, apply them as profile-specific configuration. If the profile is absent or incomplete, ask targeted questions rather than inventing durable preferences.

Use a two-pass workflow for accuracy and token efficiency:

- First pass: rank all cached papers from title, abstract, categories, authors, and comments only.
- Second pass: download or inspect source/full text only for top recommendation candidates and strong citation-check candidates.
- Do not read full source for weak matches unless the user asks for diagnostics.

Recommend up to 10 papers, but do not pad weak matches.

Do not list non-recommended papers in the user-facing recommendation report unless the user asks for diagnostics.

## Close Reading

Write reports in English by default unless the user asks for another language.

For top-ranked papers, read source, abstract page, or full text when possible. The highest-ranked entries should usually receive a deeper two- to three-paragraph English analysis explaining:

- What the paper actually does.
- Why it matches the user's profile.
- Which user paper/method/theme it connects to.
- Whether it suggests a concrete future direction.

Lower-ranked recommendations can use shorter summaries when the match is weaker or when the abstract is sufficient.

Generate research ideas sparsely. Only include ideas when a paper is genuinely promising.

Good idea pattern: combine systems, ideas, and methods across contexts, for example paper A's idea plus one method from the user's profile, paper A's system plus one concept from the user's prior work, or paper A's method plus an implementation route the user is strong in.

When a high-value idea is included in a report, also append it to `user_profile/ideas.local.jsonl` if that file exists or if the user wants persistent idea tracking. Use `user_profile/ideas.example.jsonl` as the schema. Keep idea records concise and structured:

- `source_arxiv_ids`: one or more new-paper arXiv IDs.
- `summary`: the A-plus-B idea.
- `user_connection`: the profile method, prior work, or setup that makes the idea user-specific.
- `novelty_reason`: why it is not a generic extension.
- `actionability`: the first concrete derivation, simulation, implementation, or reading step.
- `status`: start with `proposed`, then update after user feedback.

Do not promote rejected or weak ideas into durable profile preferences. Use user feedback on ideas to update `research_interests.local.md` only when it reveals a stable preference.

## Citation Check

Perform citation checks only for strongly related papers.

Inspect source `.bib`, `.bbl`, and `.tex` when available. Search for user anchor papers, user name variants, software/project names, topic phrases, and other citation anchors listed in the local profile.

For missing-citation alerts, require explicit evidence:

- A concrete overlap between the new paper and one or more user anchor papers.
- Source-level search of references or bibliography files when available.
- A short uncertainty note when the judgment is conceptual rather than direct software/method reuse.

Citation report structure:

- First section: `Needs Email`.
- Second section: `Already Cites User Work: No Email Needed`.
- Do not mention papers that neither need an email nor already cite relevant user work.

## Citation Email Style

Emails should be concise, courteous, professional, and usually indirect.

Before drafting an email, extract public contact emails from the paper source or text when available. Search `.tex`, `.bbl`, `.bib`, and extracted PDF text for `\email{...}`, `mailto:`, `email`, `corresponding author`, and raw email-address patterns. Put the best available public contact above the draft as:

```text
To: contact@example.edu
```

Prefer explicitly marked corresponding-author or `\email{...}` addresses. If several emails are found and no corresponding author is clear, list them all or choose the most likely corresponding/contact author and note the evidence in `Run Metadata`. Do not search for private contact information outside the paper/source unless the user explicitly asks.

Default subject. Use the target paper's bare arXiv identifier:

```text
On your work arXiv:XXXX.XXXXX
```

Default salutation, unless there is a specific known recipient:

```text
Dear colleagues,
```

Preferred structure:

- Open with "With great interest, I read..." and name a concrete technical point from the target paper.
- Point out common ground with the user's related work, method, or software.
- Introduce the user's work as potentially relevant, complementary, or useful context.
- Avoid directly asking for a citation unless the missing citation is exceptionally central and obvious.
- Prefer wording such as "may be useful", "might be relevant", or "in case it is helpful for a future version."

If the local profile defines topic- or software-specific email additions, include them when relevant. For example, a profile may say to mention both an original software paper and a newer white paper when the target paper uses that software; treat such entries as profile configuration, not as universal skill behavior.

## Report Format

User-facing reports should start with the useful result, not metadata.

Recommendation report:

- Start directly with the ranked recommended papers.
- Put source cache, profile files, run date, and date-convention notes under a final `Run Metadata` section.

Citation report:

- Start directly with `Needs Email`.
- Include extracted `To:` email addresses for each email-worthy paper when public contacts are present in the paper source or text.
- Put source cache, inspected files, profile files, and date notes under a final `Run Metadata` section.

If structured provenance is needed, create a sidecar JSON file such as `run_metadata.json`.

## Token And Runtime Discipline

- Use `rg` and file snippets to inspect source trees; avoid loading whole TeX projects into context.
- Prefer source `.tex`, `.bbl`, and `.bib` over PDFs when available.
- Keep non-recommended paper diagnostics out of user-facing reports unless requested.
- Put run metadata, inspected files, and source caches at the bottom or in sidecar JSON.
- In chat, return the highest-signal summary: urgent citation actions, top papers, and unusually promising ideas.

## Validation

After code changes, run:

```bash
.conda/arxiv-daily/bin/black --check src
.conda/arxiv-daily/bin/pylint src/arxiv_daily
```

After report generation, verify:

- Reports are under the arXiv source-date folder.
- Recommendation report starts with recommended papers.
- Citation report starts with email-worthy items.
- Metadata is at the bottom or in sidecar JSON.
