---
name: arxiv-daily
description: "Run the daily arXiv workflow for this project: fetch a date/category batch, recommend papers through both user-profile relevance and a rare field-level-importance screen, perform selective close reading, check missing citations, use cautious gated research-idea generation, and write user-facing reports with citation-email drafts."
---

# arXiv Daily

Use this skill for daily arXiv recommendations, close reading, cautious gated idea generation, or citation checks.

## Inputs

- Date, defaulting to the current local date.
- arXiv categories, defaulting to `quant-ph`.
- Mode: `recommend` or `recommend+citation_check`.
- Local profile files:
  - `user_profile/research_interests.local.md`
  - `user_profile/papers.local.jsonl`

## Core Rules

- Read the local profile before ranking. Use it for active topics, lower-priority topics, methods, citation anchors, email additions, and negative preferences. Do not hard-code one user's current topics in this skill.
- If the profile is absent or incomplete, ask targeted questions instead of inventing durable preferences.
- Run two independent screening tracks for every daily batch: (1) concrete value from matching the user's profile, and (2) an exceptional field-level-importance audit within the requested quantum category. The second track is an audit, not a daily recommendation quota. It normally produces zero papers and must not be used to fill, enrich, or diversify the daily list.
- Field-level importance is deliberately breakthrough-level and extraordinarily sparse: expect zero on nearly every day and roughly at most one qualifying paper in a month as an order-of-magnitude prior, never as a target. Do not include a field-level item merely because it is elegant, rigorous, general within a subfield, experimentally impressive, or more important than average. A paper may enter through either track, and a paper that truly qualifies through both appears only once with both labels.
- Rank profile-track papers by concrete value to the user, not broad keyword overlap. Rank field-level papers by prospective impact on the quantum-information field, independently of profile similarity; do not discard a genuinely important paper because it is outside the user's current direction.
- Never invent papers. Load the fetched JSON, extract actual IDs, and verify every referenced paper exists in the source data before recommending, inspecting, or reporting it.
- Recommend up to 10 papers, but do not pad weak matches or list non-recommended papers unless the user asks for diagnostics.
- Generate both Markdown and HTML reports by default unless the user explicitly asks for only one format.
- Markdown reports are English by default unless the user explicitly asks for another Markdown language. If the user gives the daily-scan request in Chinese, keep Markdown reports in English by default.
- HTML reports should optimize readability for the user's request language. If the user gives the daily-scan request in Chinese, write the HTML report UI text and summaries in Chinese by default while preserving paper titles, author names, arXiv IDs, and email drafts in their natural/original language.
- Do not spawn subagents, paper workers, or other delegated agents unless the user explicitly asks for subagents, delegation, parallel agents, or worker-based inspection in the current request. Depth, thoroughness, a full run, or daily recommendations do not count as permission to spawn subagents.

## Two Recommendation Tracks

The normal recommendation list combines two separately judged tracks. Keep the distinction visible in the report so that an out-of-profile paper is not mistaken for a profile match.

### Profile Match

Use the local profile to identify papers that are especially valuable for the user's active questions, prior work, methods, software, citation anchors, and stated preferences. Apply the ordinary relevance and staged-inspection rules below.

### Field-Level Importance

Scan the full fetched batch in the requested quantum category, including papers with weak or no profile match. This is a breakthrough-level audit for the rare paper that could alter the direction of multiple important quantum-information subfields or remove a core field-wide bottleneck. It is not a second source of ordinary recommendations and is a prospective judgment based on the paper's actual contribution, not a claim that impact has already been demonstrated. If no paper clears the gate, omit the field-level track from the user-facing report entirely.

Treat a paper as a field-level candidate only when close reading supports a concrete case such as one or more of the following, and only after the negative tests below are passed:

- A fundamental theorem, mechanism, or conceptual result that changes how a central problem is understood or resolves a significant longstanding obstacle.
- A genuinely general method, framework, or resource that opens a capability for multiple quantum-information subfields, rather than an improvement confined to one narrow setup.
- A decisive experimental demonstration that materially moves a meaningful feasibility boundary or establishes a new capability, with evidence strong enough to support broad attention.
- A result that is likely to redirect standard protocols, benchmarks, architectures, or research practice across a substantial part of the field, rather than merely reporting a small state-of-the-art gain.
- A surprising unification or observation whose consequences plausibly extend well beyond the paper's immediate model or application.

The field-level gate is a conjunction, not a checklist from which one item is enough. Before including a field-level recommendation, be able to state all of the following from the paper or its source:

- The precise central result and what is genuinely new.
- Why it can affect multiple important questions or subfields, or remove a bottleneck that is genuinely shared across the field.
- Why the result is breakthrough-level rather than merely a strong result within one subfield: identify the concrete downstream protocols, architectures, benchmarks, or research practices it could change.
- Why the claim survives a prior-art and negative-control comparison, including the strongest nearby results that make the claim look incremental.
- What decisive theorem, experiment, or cross-setting evidence supports the broad-impact claim, and what assumptions or limitations qualify it.

Apply these hard exclusions before assigning the label. Never label the following field-level importance by themselves: a new inequality or converse for a specialized problem; an abstract capacity/bound result without a clear field-wide consequence; a formal resource theory or diagnostic confined to one construction; a method demonstrated only on one model, platform, or narrow application; a modest state-of-the-art improvement; a proof-of-concept framework whose broad utility remains hypothetical; or a paper whose importance is inferred from authors, venue, title, citation absence, or fashionable keywords. For these papers, use the ordinary profile track when relevant or omit them.

Do not let a field-level label override the user's taste in an ordinary daily list. An out-of-profile paper should enter only if it clears this exceptional breakthrough gate. If the evidence is merely “important in its subfield,” “worth knowing,” or “potentially general,” it is not field-level importance.

Do not use famous authors, prestigious affiliations, a dramatic title, a press-release tone, broad keywords, a large but narrow numerical gain, or the absence of citations on a same-day paper as evidence of field-level importance. If the evidence is suggestive but does not clear the gate, keep the paper on the ordinary profile track when appropriate or omit it; do not label it a breakthrough. In reports, label qualifying entries `Field-Level Importance` or the equivalent Chinese label and state that this is a high-confidence prospective assessment. Do not use `field-changing` as an unqualified fact.

The total recommendation limit remains 10. Field-level entries count toward that limit only when the exceptional gate is cleared; they should displace a profile-match paper only in that case. If no paper clears the gate, do not report a field-level candidate, shortlist, honorable mention, or “field-level suspect” merely to show that the audit was performed.

## Fetching And Paths

Fetch metadata with the project CLI. The normal command is:

```bash
.conda/arxiv-daily/bin/arxiv-daily fetch --date YYYY-MM-DD --category quant-ph --source auto
```

`--source auto` is required for ordinary daily runs: it tries the arXiv API first and, if that fails due to network instability, HTTP errors, rate limiting, or XML/parser errors, falls back to scraping the arXiv web search result page directly.

Use these explicit variants when diagnosing fetch behavior:

```bash
.conda/arxiv-daily/bin/arxiv-daily fetch --date YYYY-MM-DD --category quant-ph --source api
```

```bash
.conda/arxiv-daily/bin/arxiv-daily fetch --date YYYY-MM-DD --category quant-ph --source html
```

`--source api` means arXiv API only. `--source html` means skip the API and read arxiv.org HTML search results directly. Use the HTML command as the manual fallback when the API is flaky but the arXiv website is reachable.

For a non-network preview of the output path and API query:

```bash
.conda/arxiv-daily/bin/arxiv-daily fetch --date YYYY-MM-DD --category quant-ph --source auto --dry-run
```

If the requested local date is fetched successfully and returns zero papers, check adjacent submitted dates and use the latest non-empty batch. Always state the date convention explicitly.

Do not use adjacent-date fallback for fetch failures until both the API attempt and the arxiv.org HTML fallback fail. If `--source auto` or the explicit `--source html` fallback still fails because of rate limiting, network errors, HTTP errors, parser errors, page-structure changes, or other non-zero command failures, report the failure directly to the user, including the requested date/category and the concrete error when available. Do not substitute a cached or adjacent-date batch unless the user explicitly asks for that fallback after seeing the failure.

When the HTML fallback is used, treat the generated JSON cache as the source of truth for recommendation work, but record in `Run Metadata` that the metadata source was `html` and that arXiv API fallback occurred. The HTML fallback uses arXiv submitted-date filtering and then verifies each parsed result against the requested submitted date; do not recommend any paper unless it appears in the generated JSON cache.

All generated paths use the arXiv source/fetch date, not the agent run date. For example, if the run date is `2026-05-21` but the latest non-empty batch is `submittedDate=2026-05-15`, all paths use `2026-05-15`.

Before starting metadata ranking, source inspection, citation checks, or report generation, check whether the resolved source date and category already have a recommendation report. If `data/reports/YYYY-MM-DD/recommendations.md` or `data/reports/YYYY-MM-DD/recommendations.html` exists and `run_metadata.json` identifies the same `source_date` and category, treat that batch as already processed. For an ordinary repeated daily request, stop after verifying the requested date has no new papers and tell the user that the latest non-empty batch already has a report, with links to the existing files. Do not reread, re-rank, redownload, or overwrite the report. Only rerun the workflow when the user explicitly requests a refresh, re-audit, updated citation check, or another material change, or when the existing report is incomplete or its metadata does not match the resolved batch.

Required path structure:

- Metadata JSON: `data/raw/arxiv/YYYY-MM-DD/quant-ph.json` or another category filename.
- Source files: `data/raw/arxiv/YYYY-MM-DD/sources/ARXIV_ID/`.
- Recommendation report: `data/reports/YYYY-MM-DD/recommendations.md`.
- HTML recommendation report: `data/reports/YYYY-MM-DD/recommendations.html`.
- Citation alerts: `data/reports/YYYY-MM-DD/citation_alerts.md`.
- Report metadata: `data/reports/YYYY-MM-DD/run_metadata.json`.
- Persistent idea log: `user_profile/ideas.local.jsonl`.

### Downloading And Extracting Sources

To programmatically download specific paper sources (source preferred, fallback to PDF) and extract/unpack them into the raw folder:

```bash
# Download and extract one or more specific paper IDs
.conda/arxiv-daily/bin/arxiv-daily download ARXIV_ID [ARXIV_ID ...]
```

Options:
- `--date`: Target arXiv submitted date, YYYY-MM-DD. If omitted, the CLI auto-resolves the paper's date by checking local metadata JSON caches first, and queries the arXiv API as a fallback.
- `--delay-seconds`: Delay in seconds between sequential downloads to prevent rate limits (defaults to `3.0`).
- `--dry-run`: Preview download actions without calling the network.

## Staged Recommendation Workflow

Use this workflow for accuracy and token efficiency:

1. Metadata pass: rank all cached papers using only metadata fields from the fetched JSON. The abstract text is stored under the `summary` key, not `abstract`; use `title`, `summary`, `categories`, `authors`, and `comment`. Verify all referenced IDs against the fetched JSON.
2. Candidate selection: choose roughly 5-12 promising profile-track papers, strong citation-check suspects, and a small number of field-level-importance suspects flagged by the metadata pass. Do not fill either track's quota with weak papers. A field-level suspect must receive source or full-text inspection even when it is not a profile match.
3. Source acquisition and inspection: the main agent downloads or reuses selected candidates' source/full text when needed using the CLI `download` command, then applies the progressive gates locally. If subagents are explicitly requested, workers may own source acquisition for their assigned papers. To reduce repeated permission prompts, the main agent may prefetch sources for the bounded candidate set before spawning workers, but should not require this when worker-side source acquisition is more natural. If, and only if, the user explicitly requests subagents or worker-based parallel inspection, spawn one paper worker per selected candidate whenever subagents are supported by the active session.
4. Final aggregation: combine the gathered evidence into one unified ranking. The main agent decides final order and writes the user-facing reports. When explicit paper workers were used, aggregate their evidence instead of treating their output as final.

Paper workers are optional, not the default. Do not spawn workers for ordinary daily-run, full-run, or quick-diagnostic requests unless the user explicitly asks for subagents, delegation, parallel agents, or workers. When workers are explicitly requested, do not spawn workers for every fetched paper; only use the bounded candidate set selected after the metadata pass.

## Main-Agent Responsibilities

- Read the profile and perform the metadata-only ranking over all cached papers.
- Perform the field-level-importance screen over the complete fetched batch, separately from profile ranking. Flag only a small number of plausible suspects for source/full-text inspection, and do not infer field-level importance from metadata alone.
- Select the bounded candidate paper set for source/full-text inspection.
- Download or inspect candidate sources locally unless the user explicitly requested subagents.
- When subagents are requested, decide explicitly whether sources are prefetched by the main agent or acquired by workers. If workers should download, say so in the worker prompt and constrain downloads to the assigned arXiv source/PDF only.
- If the user explicitly requested subagents and they are supported, spawn workers in parallel, assigning exactly one paper to each worker.
- Use `templates/paper_subagent_prompt.md` only when calling explicitly requested subagents.
- Continue non-overlapping work while explicitly requested workers inspect sources.
- Verify citation-email evidence before including it in `citation_alerts.md`.
- Follow the same staged gates locally within the main agent whenever workers are not explicitly requested, unavailable, or failed.
- Aggregate the two recommendation tracks without letting profile similarity hide a qualifying field-level paper. Mark each final paper with its track: `Profile Match`, `Field-Level Importance`, or both. Explain the field-level judgment and its caveats separately from the user-specific connection.

## Optional Paper-Worker Subagent Responsibilities

This section applies only when the user explicitly requested subagents, delegation, parallel agents, or worker-based paper inspection in the current request.

- Handle exactly one paper and return structured evidence, not a polished report.
- Apply progressive gates: relevance first, citation check only if strongly related, close reading only if genuinely promising.
- Stop early for weak or merely keyword-level matches and return a short low-priority assessment.
- Own source/full-text acquisition for the assigned paper when it is needed for close reading or citation checks. Reuse an existing `SOURCE_TREE` first; otherwise download and extract the assigned arXiv source or PDF into `data/raw/arxiv/YYYY-MM-DD/sources/ARXIV_ID/` using the CLI command: `.conda/arxiv-daily/bin/arxiv-daily download ARXIV_ID`.
- Do not install packages, use browser automation, or access unrelated network resources. If a download command needs approval, request only the minimal arXiv source/PDF fetch for the assigned paper.
- Inspect `.tex`, `.bbl`, and `.bib` snippets with `rg`; avoid loading whole source trees.
- For long LaTeX projects, read targeted sections only: abstract, introduction, main results or theorem statements, discussion/conclusion, figure captions, bibliography, and relevant appendix snippets.

## Close Reading And Ideas

For top-ranked papers, read source, abstract page, or full text when possible. The strongest profile-match entries should usually get two to three paragraphs explaining:

- What the paper actually does.
- Why it matches the user's profile.
- Which user paper, method, software, or theme it connects to.
- Whether it suggests a concrete future direction.

Use shorter summaries for weaker matches or when the abstract is sufficient.

Every paper recommended through the field-level-importance track requires enough source or full-text inspection to support the high-bar gate, even if it is not closely related to the user's work. Its summary should explain the concrete result, the mechanism or capability that may have broad consequences, the likely affected subfields or bottleneck, and the key limitations. Keep this assessment distinct from any user-profile connection.

Default to generating no research idea on a daily run. Idea generation is an exceptional outcome, not a quota and not a daily requirement. Only propose or persist an idea when the paper appears genuinely high-value after close reading and the idea passes a stricter value, feasibility, and novelty check.

Before generating an idea, do a dedicated idea-gating pass:

- Read the new paper beyond metadata: inspect the source/PDF sections needed to understand the mechanism, assumptions, limitations, and evidence. Usually inspect the abstract, introduction, main result/method section, experiments or derivations, discussion/conclusion, and relevant figures/tables or appendices.
- Read the relevant local profile material, not just the broad profile summary. Check `research_interests.local.md`, matching records in `papers.local.jsonl`, existing `ideas.local.jsonl`, and any related `data/notes/ARXIV_ID.md` notes or prior recommendation reports when they exist.
- Compare the proposed idea against the user's related prior work and existing idea log. Do not create near-duplicates, generic continuations, or ideas that only rename an existing proposal.
- Assess feasibility concretely: identify the first calculation, simulation, derivation, dataset, benchmark, observable, or software prototype; check that it fits the user's practical methods such as TensorCircuit/TensorCircuit-NG, tensor networks, Clifford/stabilizer numerics, VQA/QML workflows, or analytical derivation.
- Assess novelty concretely: explain why the combination is not a routine application of the paper's own setup or a generic "apply to nearby model" extension. Prefer crossed A-plus-B combinations where the new paper supplies a mechanism or method and the user's profile supplies a distinct system, diagnostic, software route, or prior result.
- If any of value, feasibility, or novelty is uncertain after this pass, do not create a persistent idea. Mention at most a tentative reading note in the recommendation text, clearly marked as not promoted to `ideas.local.jsonl`.

Good ideas combine the new paper's system, technique, or observation with a user-specific method, prior work, setup, or implementation route. Avoid generic extensions such as adding noise, changing systems, or doing larger numerics without a concrete nontrivial reason.

Idea records should be specific enough to retrieve and refine later. Define the proposed diagnostic, model, comparison class, observable, or first calculation instead of only naming a broad theme. Include evidence from the gating pass in `notes` or another concise field: cite the recommendation report date plus the inspected paper section, local note, related prior user paper, existing idea comparison, or source snippet that supports feasibility and novelty.

When a high-value idea is included and persistent idea tracking exists or is requested, append a concise record to `user_profile/ideas.local.jsonl` using `user_profile/ideas.example.jsonl` as the schema:

- `source_arxiv_ids`
- `summary`
- `user_connection`
- `novelty_reason`
- `actionability`
- `status`, starting as `proposed`

Do not promote rejected, weak, duplicate, or merely plausible ideas into `ideas.local.jsonl` or durable profile preferences. Update `research_interests.local.md` from idea feedback only when it reveals a stable preference.

## Citation Checks

Run citation checks only for strongly related papers. Search source `.tex`, `.bbl`, and `.bib` files when available, using user anchor papers, user-name variants, software/project names, topic phrases, and other anchors from the profile.

Create citation emails only when all three conditions hold:

- Direct method/software reuse: the paper uses the same method, algorithm, or software framework the user developed.
- Same-problem-space relation: the paper directly builds on, extends, compares against, or competes with the user's work in the same technical setting.
- Obvious missing citation: a domain expert would expect the user's work as a standard reference for that specific method or problem.

Do not create citation alerts for broad keyword overlap, indirect conceptual relevance, or different implementations/frameworks unless the user's framework is the standard tool for that task.

Profile-specific citation rules may strengthen these defaults. If the local profile says a field-originating paper is a priority anchor, follow that rule. For QAS, when the profile identifies "Differentiable quantum architecture search" as the first work to introduce the QAS concept, treat papers that propose, use, survey, benchmark, or position quantum architecture search or AutoML/NAS-style quantum circuit architecture design without citing DQAS as likely `Needs Email`, unless the mention is only incidental.

For every missing-citation alert, include:

- Concrete technical relation to one or more user anchor papers.
- Source-level reference or bibliography search evidence when available.
- A short uncertainty note when the judgment is conceptual rather than direct software/method reuse or concept similarity.

Citation reports contain only:

- `Needs Email`
- `Already Cites User Work: No Email Needed`

Do not mention papers that neither need an email nor already cite relevant user work.

## Citation Email Style

- **Bibliographic Integrity**: To prevent hallucination of author names, publications, or journals in the email drafts, the agent MUST explicitly lookup the exact bibliographic metadata of the relevant prior paper from `user_profile/papers.local.jsonl` (using a keyword or title query) rather than relying on parametric memory.

Before drafting, extract public contact emails from the paper source or text when available. Search `.tex`, `.bbl`, `.bib`, and extracted PDF text for `\email{...}`, `mailto:`, `email`, `corresponding author`, and raw email patterns. Do not search for private contact information outside the paper/source unless the user explicitly asks.

Put the best public contact above the draft:

```text
To: contact@example.edu
```

Prefer corresponding-author or `\email{...}` addresses. If several emails are found and no corresponding author is clear, list them all or choose the most likely contact and note the evidence in `Run Metadata`.

Use this default subject with the target paper's bare arXiv ID:

```text
On your work arXiv:XXXX.XXXXX
```

Use this default salutation unless a specific recipient is known:

```text
Dear colleagues,
```

Emails should be concise, courteous, professional, and usually indirect:

- Open with `With great interest, I read...` and name a concrete technical point from the target paper.
- Do not explicitly say `overlap`, `overlaps with our work`, or similar direct phrasing in the email body.
- Instead, describe the target paper's theme or technical emphasis, then introduce the user's related work as complementary context, a potentially useful reference, or an additional perspective.
- Prefer phrases such as `related context`, `complementary perspective`, `may provide a useful angle`, or `in case it is helpful for a future version`.
- Avoid directly asking for a citation unless the omission is exceptionally central and obvious.
- Prefer wording such as `may be useful`, `might be relevant`, or `in case it is helpful for a future version`.
- Include profile-defined topic or software email additions when relevant.
- For QAS-related emails, if the local profile specifies DQAS as the first paper to introduce quantum architecture search, explicitly say this in the draft while keeping the tone courteous. Example: `To the best of my knowledge, our DQAS paper was the first work to introduce the quantum architecture search (QAS) concept, and it may provide useful background for your discussion.`

## Report Format

User-facing reports start with useful results, not metadata.

Generate Markdown and HTML reports in parallel unless the user explicitly asks for only one format. Use the embedded template at `templates/daily_report_template.html` as the only source of truth for the HTML visual structure and styling. The generated HTML should be plain static HTML with no external JavaScript or remote assets.

Language defaults:

- Markdown `recommendations.md` and `citation_alerts.md`: English by default, including when the user request is in Chinese, unless the user explicitly asks for Chinese Markdown.
- HTML `recommendations.html`: follow the user's request language for readability. For Chinese daily-scan requests, use Chinese section labels, priority labels, action labels, and recommendation prose; keep paper titles, author names, arXiv IDs, technical terms where clearer, and citation email drafts in their natural/original language.

HTML recommendation report requirements:

- Write `data/reports/YYYY-MM-DD/recommendations.html`.
- Set the HTML document title and main `<h1>` to `Everyday arXiv 推荐`.
- Include a top-list table before detailed paper cards.
- Use bare arXiv IDs without version suffixes in HTML visible text and same-page anchors, for example `2605.22555`, `href="#paper-2605-22555"`, and `id="paper-2605-22555"`.
- Include direct arXiv links for every recommended paper, normally `https://arxiv.org/abs/ARXIV_ID` and a PDF link `https://arxiv.org/pdf/ARXIV_ID`, using the bare ID without `vN`.
- Include priority/action badges such as high, medium, low, or citation alert; do not overstate priority for weak matches.
- Include the sparse research-idea box only when there is a genuinely high-value idea.
- Do not put run metadata, source cache, profile files, or date-convention notes at the bottom of HTML reports. Keep provenance in Markdown `Run Metadata` sections and/or `run_metadata.json`.

HTML citation report requirements:

- Do not create a separate HTML citation report by default. If citation alerts exist, merge them into `recommendations.html` as a citation-alert section.
- Include arXiv links for each cited target paper and same-page anchors from any citation-alert summary to the detailed citation card, using bare arXiv IDs without version suffixes in visible text and anchors.
- Keep HTML citation-alert prose concise: say that the relevant user work is not cited and why the target paper is in scope. Do not include detailed source-search, grep, or bibliography-search diagnostics in HTML; keep that evidence in Markdown `citation_alerts.md` and/or `run_metadata.json`.
- Preserve the email draft formatting using a `<pre>` or equivalent preformatted block.

Recommendation reports:

- Start directly with ranked recommended papers.
- Make the recommendation track visible for every paper (`Profile Match`, `Field-Level Importance`, or both). Keep field-level papers prominent even when their user-profile relevance is weak, and explain their prospective broad impact in a dedicated sentence or paragraph.
- Put source cache, profile files, run date, and date-convention notes under a final `Run Metadata` section.

Citation reports:

- Start directly with `Needs Email`.
- Include extracted `To:` email addresses for email-worthy papers when public contacts are present.
- Put source cache, inspected files, profile files, and date notes under a final `Run Metadata` section.

If structured provenance is useful, create a sidecar `run_metadata.json`.

## Token And Runtime Discipline

- Use `rg` and file snippets for source inspection.
- Prefer source `.tex`, `.bbl`, and `.bib` over PDFs when available.
- Avoid loading whole TeX projects into context.
- Keep non-recommended diagnostics out of reports unless requested.
- In chat, return only the highest-signal summary: urgent citation actions, top papers, and unusually promising ideas.

## Validation

After code changes, run:

```bash
.conda/arxiv-daily/bin/pytest -q tests
.conda/arxiv-daily/bin/black --check src tests
.conda/arxiv-daily/bin/pylint src/arxiv_daily
```

After report generation, verify:

- Reports are under the arXiv source-date folder.
- `recommendations.html` exists, is titled `Everyday arXiv 推荐`, and its top-list links jump to matching paper-card IDs.
- HTML visible arXiv IDs and same-page anchors use bare IDs without `vN` suffixes.
- Each recommended paper in the HTML includes an arXiv abstract-page link.
- HTML reports do not include bottom metadata/footer provenance blocks.
- Recommendation report starts with recommended papers.
- Field-level recommendations, when present, have an explicit track label and a concrete evidence-and-limitations explanation; an ordinary daily report does not imply that one must be present.
- Citation report starts with email-worthy items.
- Markdown metadata is at the bottom or metadata is in sidecar JSON.
