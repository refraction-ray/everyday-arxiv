---
name: user-bootstrap
description: Initialize or refresh this project's private user profile from Google Scholar or user-provided publication data, filter non-article records, and produce a research-interests profile through evidence-based synthesis and targeted user questions.
---

# User Bootstrap

Use this skill when initializing or updating `user_profile/` for the arXiv Daily assistant.

The goal is to create two durable private files:

- `user_profile/papers.local.jsonl`: prior formal papers/preprints for matching and citation checks.
- `user_profile/research_interests.local.md`: current research interests, methods, taste, skills, and negative preferences.

Keep public templates generic. User-specific outputs are private and must use `*.local.*` names.

## Inputs

Accept any combination of:

- A Google Scholar profile URL or a Scholar search/login URL plus a resolved `--user-id`.
- User-provided paper lists, BibTeX, titles, abstracts, or publication pages.
- Existing `user_profile/papers.local.jsonl`.
- Direct user notes about research interests, methods, preferences, and active projects.

## Step 1: Read Project Rules

Before doing work, read:

- `agents.md`
- `docs/prd.md`
- `user_profile/README.md`
- `user_profile/research_interests.template.md`
- `user_profile/papers.example.jsonl`

Respect the open-source boundary. Do not move private user data into public templates.

## Step 2: Bootstrap Papers

Prefer the project CLI for Google Scholar:

```bash
.conda/arxiv-daily/bin/arxiv-daily profile bootstrap-scholar '<scholar-url>' --user-id '<user-id-if-needed>'
```

Useful options:

- `--delay-seconds N`: slow down per-paper detail requests.
- `--no-details`: export list metadata only if Scholar is rate-limiting.
- `--from-html path/to/profile.local.html`: parse a user-saved complete profile page without live requests.
- `--include-non-articles`: include patents, conference abstracts, and unknown records only if the user explicitly wants them in the matching profile.

Default behavior should exclude non-article records from `papers.local.jsonl` while preserving them in `google_scholar.local.json`.

Exclude by default:

- Patents and patent applications.
- APS March Meeting abstracts.
- Bulletin of the American Physical Society records.
- Records with no usable venue/source evidence.

Keep excluded records in `user_profile/google_scholar.local.json` under `all_records` for auditability.

## Step 3: Handle Scholar Rate Limits

Google Scholar rate-limits automated access. Treat HTTP 429 and "Our systems have detected unusual traffic" pages as expected failure modes, not empty profiles.

If blocked:

- Do not retry aggressively.
- Tell the user exactly what happened.
- Suggest waiting, increasing `--delay-seconds`, using `--no-details`, or saving the public profile HTML and using `--from-html`.
- Preserve any successful local outputs and report missing abstracts or failed detail pages.

## Step 4: Inspect Imported Papers

After import, summarize:

- Number of records in `papers.local.jsonl`.
- Number of raw Scholar records.
- Number and type of excluded records.
- Number of formal papers missing abstracts.
- Most cited and most recent paper clusters.
- Obvious duplicate or suspicious records.

Use the raw export for audit, but use `papers.local.jsonl` as the matching profile.

## Step 5: Infer arXiv Category Candidates

After inspecting the imported papers, infer a short candidate list of arXiv
categories that should drive the daily fetch configuration.

Base the category suggestions on:

- Repeated themes, methods, and venues in `papers.local.jsonl`.
- Explicit arXiv evidence when available in paper URLs, IDs, abstracts, or notes.
- The user's current active interests from any existing
  `research_interests.local.md`.
- The project default of `quant-ph`, which should remain only when supported by
  the evidence or when the user confirms it as a broad default.

Present the candidates with concise evidence and tradeoffs before writing any
configuration. For example:

```text
Your imported papers point most strongly to quantum information and condensed
matter theory. For daily arXiv fetching, should I set default_categories to
["quant-ph"], ["quant-ph", "cond-mat.str-el"], or another list?
```

Do not silently choose broad or expensive category sets. Ask the user which
arXiv categories they want monitored for daily recommendations, especially
when the inferred themes span multiple arXiv areas.

When the user confirms the category list, write it to the private local config:

```toml
[arxiv]
default_categories = ["quant-ph", "cond-mat.mes-hall"]
```

Use `config/local.toml` for this update. Preserve unrelated existing local
settings. Never write user-specific category choices into `config/default.toml`
or `config/local.example.toml`.

If the user is unsure, record the uncertainty in
`research_interests.local.md` and keep the current config unchanged.

## Step 6: Generate Research Interests

Create or update `user_profile/research_interests.local.md`.

Base the draft on:

- Titles, abstracts, venues, years, and citation counts from `papers.local.jsonl`.
- User-provided notes and corrections.
- Existing `research_interests.local.md`, preserving dated history unless explicitly superseded.

The file should include:

- Active interests.
- Prior work themes.
- Methods and skills.
- Keywords.
- Citation-check anchor papers.
- Negative preferences and low-value directions to avoid.
- Feedback log with dates.

Do not overfit to old highly cited papers if recent papers show a different direction. Distinguish established expertise from current active interests.

## Step 7: Ask Targeted Questions

If important profile choices are uncertain, ask the user before finalizing. Prefer a small number of high-value questions rather than a long survey.

Ask when uncertain about:

- Which arXiv categories should be monitored by default for daily recommendations.
- Which themes are currently active versus historical.
- Whether software/tooling papers should drive daily recommendations or mainly serve citation checks.
- Which methods the user personally wants to use.
- Which paper families should be treated as citation-check anchors.
- Whether excluded patents or conference abstracts should influence the profile.
- Which generic extensions the user considers low-value.

Good question style:

```text
I see three strong clusters: <cluster A>, <cluster B>, and <cluster C>. Which of these should dominate daily recommendations for the next few months?
```

This is only an example of a concise cluster-prioritization question. Replace the topics with clusters actually supported by the user's imported papers and notes.

Do not invent private preferences when the evidence is ambiguous. Mark uncertain in the profile or ask.

## Step 8: Write The Profile

When writing `research_interests.local.md`:

- Preserve existing useful content.
- Add a dated update entry.
- Separate inferred interests from user-confirmed interests when needed.
- Keep wording operational for future recommendation agents.
- Include negative guidance against banal idea generation.

A good profile should help the ArXiv Daily skill answer:

- Which papers are worth reading today?
- Which prior user papers might a new paper need to cite?
- Which new-paper-plus-user-work combinations are nontrivially promising?
- Which ideas should be rejected as too incremental?

## Step 9: Validation

After code changes, run:

```bash
.conda/arxiv-daily/bin/black --check src
.conda/arxiv-daily/bin/pylint src/arxiv_daily
```

After profile changes, report:

- Files written.
- Data source used.
- Excluded record count.
- Missing abstract count.
- Confirmed arXiv categories written to `config/local.toml`, or the reason no
  local category config was changed.
- Questions still needing user judgment.
