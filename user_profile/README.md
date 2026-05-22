# User Profile

This directory stores durable user context for arXiv recommendation and citation-check workflows.

## Files

- `research_interests.template.md`: public structure and generic defaults.
- `research_interests.local.md`: private user profile for agents. Gitignored.
- `papers.local.jsonl`: private previous papers, one JSON object per line. Gitignored.
- `ideas.local.jsonl`: private sparse research-idea log, one JSON object per proposed idea. Gitignored.
- `feedback.local.jsonl`: private sparse feedback log for papers and ideas. Gitignored.
- `papers.example.jsonl`: example schema for `papers.local.jsonl`.
- `ideas.example.jsonl`: example schema for `ideas.local.jsonl`.
- `feedback.example.jsonl`: example schema for `feedback.local.jsonl`.

Legacy or convenience files named `papers.jsonl` are also treated as private and gitignored.

## Updating Rules

Prefer additive updates with dates. Do not overwrite older interests unless the user explicitly says they are obsolete.

When the user evaluates a recommendation or idea, first record the raw signal in `feedback.local.jsonl` with a simple score:

- `2`: strongly positive.
- `1`: mildly positive/useful.
- `0`: neutral or unclear.
- `-1`: mildly negative/not useful.
- `-2`: strongly negative.

Only promote feedback into `research_interests.local.md` when the user explicitly says to remember it or when repeated feedback shows a stable pattern, especially:

- topics the user wants more of,
- topics the user considers low-value,
- methods the user can apply,
- paper combinations that look promising,
- paper combinations the user rejects as too incremental.

Idea records should stay sparse. Do not log every weak thought; log only ideas that are concrete enough to have a first technical action and distinctive enough to avoid generic "apply method X to nearby system Y" extensions.
