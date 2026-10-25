# arXiv Daily Agent Guide

This project supports a daily arXiv reading workflow for quantum-information research.

The product requirements are recorded in `docs/prd.md`. Treat that file as the durable source for the user's original goals when session context is unavailable.

## Core Principle

The Python code is responsible for deterministic tasks: fetching arXiv metadata, parsing papers, caching results, and producing stable machine-readable files. The agent is responsible for judgment-heavy tasks: interest matching, close reading, citation checks, research-idea generation, and user-profile updates.

## User Profile

Read `user_profile/` before making recommendations.

- `research_interests.template.md` documents the public profile structure.
- `research_interests.local.md` stores the user's private current interests, methods, taste, and negative preferences.
- `papers.local.jsonl` stores the user's private prior papers, one JSON object per line.
- `papers.example.jsonl` documents the expected paper-record schema.
- `ideas.local.jsonl` stores sparse private research ideas when persistent idea tracking is enabled.
- `ideas.example.jsonl` documents the expected idea-record schema.
- `google_scholar.local.json` stores the private raw Google Scholar bootstrap export when generated.

Files matching `*.local.*` are private and must not be committed. Public templates should contain structure and generic examples only.

When updating the profile, preserve old information unless the user explicitly supersedes it. Add dated notes rather than silently rewriting the user's research taste.

## Project Skills

Specific operational workflows are implemented as project-local skills:

- `.agents/skills/user-bootstrap/SKILL.md`: initialize `user_profile/` from Google Scholar or user-provided publication data and generate research interests.
- `.agents/skills/arxiv-daily/SKILL.md`: fetch arXiv papers, recommend papers, do close reading, run citation checks, and write reports.
- `.agents/skills/feedback-memory/SKILL.md`: record sparse user feedback on papers and ideas, update idea status, and promote stable feedback patterns into the private research profile.

Keep `agents.md` focused on project-wide environment, privacy boundaries, and high-level architecture. Put detailed daily workflow rules in the corresponding Skill.

## Open-Source Boundary

The repository should remain publishable.

- Commit generic workflow docs, templates, code, and default config.
- Do not commit user-specific papers, interests, idea logs, Google Scholar exports, reports, raw arXiv caches, PDFs, or generated analysis.
- Use `config/local.toml` for machine-specific or user-specific configuration overrides.
- Use `user_profile/*.local.*` for private profile material.
- Public code must work without local files by falling back to templates and defaults.

## Environment And Checks

Use the project-local Conda environment when running Python tooling:

```bash
conda activate .conda/arxiv-daily
```

The environment is defined by `environment.yml` and should include Python 3.11, pytest, Black, Pylint, and pip.

For commands that do not activate the environment, use the environment's Python directly:

```bash
.conda/arxiv-daily/bin/python -m arxiv_daily.cli fetch --dry-run
```

Before handing off code changes, run:

```bash
.conda/arxiv-daily/bin/pytest -q tests
.conda/arxiv-daily/bin/black --check src tests
.conda/arxiv-daily/bin/pylint src/arxiv_daily
```

If package metadata is needed for console scripts or imports without `PYTHONPATH`, install the project in editable mode:

```bash
.conda/arxiv-daily/bin/python -m pip install -e .
```

## Defaults

- Default arXiv category: `quant-ph`.
- Default date: local current date used by the CLI.
- Every fetch selects by **announcement date**: the batch arXiv published on that date, which is what a reader sees on the listing page. This is the one primary selection; a `submittedDate` slice exists only as the labelled degraded fallback described below. Announcement batches are the only way to include weekend and moderator-held submissions, which are announced together with the next batch, and arXiv's API publishes no announcement-date field at all.
- The current batch comes from `arxiv.org/list/<category>/new`; an older one from that date's catch-up page `arxiv.org/catchup/<category>/YYYY-MM-DD`, which arXiv keeps for the past 90 days. A date with no announcement (weekend or holiday) is an error rather than an empty cache.
- A batch is every paper **first announced** that day in the category: its new submissions plus its cross-lists (papers whose primary category is elsewhere), each tagged with `listing_section: "new"` or `"cross"`. Replacements are excluded, and so are cross-lists of papers announced on an earlier day that only now gained the category; those are detected by arXiv ID against the previous batch, and the cache `query` field lists them.
- A date older than the catch-up window is fetched as a **degraded fallback**: if no cache exists for it, the CLI calls the arXiv API for a `submittedDate` slice of that UTC day and writes `source: "api-submitted-slice"` with `date_convention: "submitted_date_slice"`. That is not the announcement batch, so the Markdown report and the user-facing reply must say which convention was used and what the slice misses. If a cache already exists for that date, the CLI refuses rather than overwriting a batch with a slice.
- Listing and catch-up pages are requested with `abs=True`, so titles, authors, comments and abstracts come from the page itself and a batch fetch never depends on the API. The API is used only for the optional enrichment that replaces the announcement-date placeholder with real submission timestamps, and for the out-of-window slice; `--no-api` disables both, which is the right choice on networks where `export.arxiv.org` is unreachable.
- The whole batch is collected. `--max-results` is an explicit cap, and the CLI says so when it truncates.
- Never infer a paper count from `len(json.load(...))` on a metadata cache: the top-level JSON is an object of metadata fields wrapping the paper list. Read its `count` field or `len(payload["papers"])`.
