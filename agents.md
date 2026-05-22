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
- arXiv date filtering uses `submittedDate` ranges in `YYYYMMDD0000` to `YYYYMMDD2359`.
- When the HTML fallback is used, only papers whose first version (`v1 submitted`) matches the target date should be included; later revisions on that date are not part of the daily first-submission batch.
