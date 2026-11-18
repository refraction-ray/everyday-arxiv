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

- Read the local profile before ranking: active and lower-priority topics, methods, citation anchors, email additions, negative preferences. If it is absent or incomplete, ask targeted questions instead of inventing durable preferences.
- Run the two screening tracks of the next section independently — concrete value to the user, and the sparse field-level-importance audit — and rank each by its own criterion rather than by broad keyword overlap.
- Never invent papers: load the fetched JSON, extract actual IDs, and verify every referenced paper exists there before recommending, inspecting or reporting it.
- Recommend up to 10 papers; do not pad weak matches, and do not list non-recommended papers unless the user asks for diagnostics.
- Do not spawn subagents, paper workers or other delegated agents unless the user explicitly asks for them. Depth, thoroughness, a full run or a daily recommendation do not count as permission.

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

Field-level entries count toward the same limit only when that gate is cleared, and displace a profile-match paper only then. If nothing clears it, do not report a candidate, shortlist, honorable mention or “field-level suspect” merely to show the audit was performed.

## Fetching And Paths

Fetch metadata with the project CLI. The normal command is:

```bash
.conda/arxiv-daily/bin/arxiv-daily fetch --date YYYY-MM-DD --category quant-ph
```

Every fetch selects by **announcement date**: the batch arXiv published on the requested date, which is what a reader actually sees on the listing page that day. That is the one primary selection, because arXiv's API publishes no announcement-date field and `submittedDate` is a UTC submission timestamp that only partly overlaps the batch (a submitted-date slice is used only as the labelled fallback described below):

- Weekend and moderator-held submissions are announced together with the following batch, so a Monday announcement batch routinely contains papers submitted on Friday, Saturday, and Sunday.
- A submission-date window therefore misses 30-50% of a Monday batch, and it also includes same-day submissions that will only be announced the next day.
- Before the 20:00 ET announcement, the current date has no batch at all; that is expected, not a fetch failure.

**Which page serves the date.** The requested date is read from its **catch-up page** (`arxiv.org/catchup/<category>/YYYY-MM-DD`), which is indexed by announcement date and needs no pagination. `arxiv.org/list/<category>/new` mirrors only the newest batch and is regenerated later than the catch-up index, so the CLI uses it for two things only: naming the newest batch when the requested date has none, and serving that batch when the catch-up page is still empty. Do not conclude that a date has no batch from a listing page whose printed date is older — on 2026-11-16 the listing still showed the 2026-11-13 batch while the 2026-11-16 catch-up page already held the complete batch. Both pages are requested with `abs=True` and both have their printed announcement date verified, so titles, authors, comments and abstracts come from the page and a batch fetch never depends on the API.

**What a batch is.** Every paper first announced that day: the page's new submissions plus its cross-lists, tagged in the cache as `listing_section: "new"` or `"cross"`. Replacements are excluded. The cross-list section also carries papers announced on an earlier day that only now gained the category; the CLI filters those locally, without reading a second page. A cross-list survives when its ID is at or above the batch's first new submission, or when it shares its `YYMM` with the batch's newest new submission — the same-month test keeps a genuine new cross-list submitted just before the batch's first new submission (2026-11-16: `2611.17366`), and keeps a first-of-month batch, whose submissions all carry the previous month's `YYMM`. Dropped IDs are recorded in the cache `query` field.

**Stale copies, and pages that grow.** Both pages are cached by arXiv's CDN in copies keyed on `Accept-Encoding`, and the copies go stale at different times: on 2026-11-16 the compressed copy of one catch-up URL listed 44 new submissions while the uncompressed copy listed 64, each internally consistent with its own `(showing N of N entries)` figures, so nothing errors and the batch is silently undercounted. The client therefore requests `Accept-Encoding: identity`; a cache that carries 51 papers is the stale copy. A page can also gain entries later in the same day, so a same-day count is a snapshot, not a final figure: the same page went from 128 entries (`New 64`, `Cross 10`, `Replacement 54`) at 11:00 to 131 (`New 65`, `Cross 10`, `Replacement 56`) at 12:20, the addition being a submission from the previous Friday evening. If a count is in doubt, re-read the page and compare it against the figures the page prints.

**Two hard limits.** arXiv serves catch-up pages only for the past 90 days, and a date on which arXiv announced nothing has no batch, so no empty cache is written. A catch-up request outside the window answers HTTP 400, and so does a request for a future date; the CLI tells them apart by comparing the requested date with the newest batch, and reports a missing batch as a single-line message naming that newest batch.

A date older than the 90-day window cannot be rebuilt as a batch, because the API has no announcement-date field. For that case the CLI degrades to a **submitted-date slice**: it calls the arXiv API for `submittedDate=[D0000 TO D2359]` and writes the result with `source: "api-submitted-slice"` and `date_convention: "submitted_date_slice"`. This fallback only fires when no cache exists for that date; if one does, the CLI refuses rather than overwriting an announcement batch with a slice. A slice is not the batch, so:

- Say so explicitly at the top of the Markdown report and in `Run Metadata`, naming the convention and what it misses: papers announced that day but submitted on earlier days (weekend and moderator-held submissions), plus papers submitted that day that belong to the next day's batch.
- Say so in your chat reply to the user, in the first sentence about the batch.
- Never compare its `count` against a listing `(showing N of N entries)` figure, and never let it silently become the "today's arXiv" baseline.

The only other role of the API (`export.arxiv.org`) is optional enrichment, which replaces the announcement-date placeholder with real submission timestamps; `--no-api` disables that and the slice, and is the right choice on networks where the host is unreachable. When enrichment fails the fetch still succeeds, the cache `query` records the error, and `published`/`updated` hold the announcement date.

The whole batch is always collected. `--max-results N` is an explicit cap: the CLI prints a warning and appends `[truncated to N of M papers]` to the cache `query` field, so a capped cache can never be mistaken for a complete batch.

For fetch failures (rate limiting, network errors, HTTP errors, parser errors, changed page structure), report the failure directly to the user with the requested date/category and the concrete error. Do not substitute a cached or adjacent-date batch unless the user explicitly asks for that after seeing the failure.

Treat the generated JSON cache as the source of truth for recommendation work, and record it in `Run Metadata`: `source` is `catchup` for the normal path, `list` when the catch-up page was empty and the listing served the newest batch, and `api-submitted-slice` for the out-of-window fallback, whose `date_convention` is then `submitted_date_slice`; the `query` field holds the URLs or search query actually used plus any excluded-cross-list, enrichment or truncation note. Do not recommend any paper unless it appears in the generated JSON cache.

All generated paths use the announcement date, not the agent run date. That date is what the user means by "today's arXiv".

Before starting metadata ranking, source inspection, citation checks, or report generation, check whether the resolved source date and category already have a recommendation report. If `data/reports/YYYY-MM-DD/recommendations.md` or `data/reports/YYYY-MM-DD/recommendations.html` exists and `run_metadata.json` identifies the same `source_date` and category, treat that batch as already processed. For an ordinary daily request on a date with no batch yet (before the announcement, or a weekend/holiday), the CLI refuses and its message names the newest batch date; if that newest batch already has a report, stop and tell the user so, with links to the existing files. Do not reread, re-rank, redownload, or overwrite the report. Only rerun the workflow when the user explicitly requests a refresh, re-audit, updated citation check, or another material change, or when the existing report is incomplete or its metadata does not match the resolved batch.

Required path structure:

- Metadata JSON: `data/raw/arxiv/YYYY-MM-DD/quant-ph.json` or another category filename.
- Source files: `data/raw/arxiv/YYYY-MM-DD/sources/ARXIV_ID/`, where `ARXIV_ID` is the bare ID without a `vN` suffix.
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
- `--date`: Batch date, i.e. the date folder the source tree is written under, YYYY-MM-DD. If omitted, the CLI scans every date folder under the raw arXiv directory, ignoring version suffixes: a `list`/`catchup` batch cache that lists the paper wins, then any older cache, then an existing `sources/<id>` folder, with the earliest date winning within each rank. Only when nothing local matches does it query the arXiv API, whose date is the v1 *submission* date rather than an announcement date.
- `--delay-seconds`: Delay in seconds between sequential downloads to prevent rate limits (defaults to `3.0`).
- `--dry-run`: Preview download actions without calling the network.

## Staged Recommendation Workflow

1. **Metadata pass.** Rank every cached paper from metadata only. The abstract lives under `summary`, not `abstract`; use `title`, `summary`, `categories`, `authors`, `comment`, and verify every referenced ID against the fetched JSON.
2. **Screening.** Over the *complete* batch, run the field-level-importance screen separately from profile ranking — metadata may flag a suspect but cannot establish field-level importance. Then pick a bounded candidate set: roughly 5-12 profile-track papers, the citation-check suspects, and those few field-level suspects. Do not pad either track with weak papers.
3. **Source inspection.** Download or reuse the candidates' sources with the CLI `download` command and apply the progressive gates locally. While reading each source, record its provenance from the title block (`\affiliation`, `\institute`, `\email`); the local profile decides what a weak or missing affiliation means for the shortlist, and that test only removes papers — a prestigious affiliation, author or title is never positive evidence of importance.
4. **Aggregation.** Write one unified ranking. Mark each paper `Profile Match`, `Field-Level Importance`, or both; keep a qualifying field-level paper visible even when profile similarity is low; and verify citation-email evidence in the sources before it reaches `citation_alerts.md`.

Paper workers are optional, not the default: spawn them only when the user explicitly asks for subagents, delegation, parallel agents or workers, and only for the bounded candidate set — never one per fetched paper.

## Optional Paper-Worker Subagent Responsibilities

This section applies only when the user explicitly requested subagents, delegation, parallel agents, or worker-based paper inspection in the current request. Call them with `templates/paper_subagent_prompt.md`.

- Handle exactly one paper and return structured evidence, not a polished report.
- The main agent decides whether it prefetches sources for the candidate set (fewer permission prompts) or lets workers acquire their own, says which in the worker prompt, and constrains downloads to the assigned paper. Keep non-overlapping work going while workers inspect, then aggregate their evidence instead of treating it as final.
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

Where the local profile states its own citation-email style — subject, salutation, sign-off, topic-specific additions — the profile wins; the defaults below apply only where it is silent.

- **Bibliographic integrity.** Look up every cited prior paper's exact metadata in `user_profile/papers.local.jsonl` (keyword or title query) instead of relying on memory, so author lists, venues and years in the draft are the user's real ones.
- **Contact address.** Extract a public contact from the paper's own source or text: `\email{...}`, `mailto:`, `corresponding author`, and raw address patterns in `.tex`, `.bbl`, `.bib`, or the extracted PDF text. Prefer the corresponding author's `\email{...}`; if several are equally likely, list them or pick the most likely and note the evidence in `Run Metadata`. Do not look for private contact information outside the paper unless the user asks.
- **Format.** Put the best contact above the draft as `To: contact@example.edu`. Default subject `On your work arXiv:XXXX.XXXXX` with the bare ID; default salutation `Dear colleagues,`.
- **No manual line wrapping.** Write each paragraph of the email body as one unbroken line and let the recipient's client wrap it. Do not insert hard newlines at a fixed column — the draft is copied out and pasted into a mail client, where pre-wrapped lines produce ragged text.
- **Brief description of the target.** Describe the recipient's work in one short clause: what was read and the single point of interest. Do not paraphrase the abstract, list its results, or spend more than one sentence on it; the draft is about the connection, not a summary of their paper.
- **Tone.** Concise, courteous, indirect. Open with `With great interest, I read...` and one concrete technical point from the target paper, then describe its theme and introduce the user's own work as complementary context — `related context`, `complementary perspective`, `may provide a useful angle`, `in case it is helpful for a future version`. Never write "overlap", and do not ask for a citation outright unless the omission is exceptional and obvious.
- **Priority anchors.** When the profile designates a paper as a priority anchor for the target's topic (first to introduce a concept, standard software for a task), say so plainly and courteously, e.g. "to the best of my knowledge, our X was the first work to introduce ...". The profile carries the wording rules per anchor.

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

Markdown reports:

- `recommendations.md` starts with the ranked papers, each labelled `Profile Match`, `Field-Level Importance`, or both — a field-level paper stays prominent even when its profile relevance is weak, with its prospective broad impact in its own sentence.
- `citation_alerts.md` starts with `Needs Email`, then `Already Cites User Work: No Email Needed`, and carries the extracted `To:` addresses.
- Both end with a `Run Metadata` section — source cache, inspected files, profile files, run date, date-convention notes — mirrored by the sidecar `run_metadata.json`.

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

- Reports sit under the source-date folder, and `count` matches the page figures: `New` + `Cross` from the page named in `query`, minus any cross-lists the note lists. A `submitted_date_slice` cache has no such figure to compare, and a cache whose `query` carries a truncation or enrichment note is not a plain complete batch.
- `recommendations.html` is titled `Everyday arXiv 推荐`, its top list jumps to matching card ids, visible IDs and anchors are bare (no `vN`), every paper has an abstract-page link, and there is no bottom provenance block.
- `recommendations.md` opens with the ranking and labels each paper's track; `citation_alerts.md` opens with `Needs Email`; both end in `Run Metadata` or a sidecar `run_metadata.json`.
