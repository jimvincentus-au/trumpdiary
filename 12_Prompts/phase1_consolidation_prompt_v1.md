# Trump Diary — Phase 1 Consolidation Prompt v1

You are consolidating overlapping Phase 1 window-level candidate thread outputs into one **year-wide canonical thread catalogue** for **The Trump Diary**.

Your task is to read the supplied consolidation input package and produce a JSON object that conforms to:

`phase1_consolidated_thread_catalog.schema.json`

## Purpose

This is the **cross-window consolidation step**.

The Phase 1 discovery step has already been completed independently for each overlapping window. Those window outputs are intentionally local and partially redundant. Your job now is to:

- merge duplicate or near-duplicate candidate threads across windows
- normalize canonical names
- decide where hierarchy is genuinely warranted
- preserve real late-emerging threads
- reject weak or redundant candidate labels
- produce one stable year-wide canonical catalogue

You are no longer working window-by-window. You are working across the full supplied evidence base.

## What you are consolidating

The input package contains multiple window-level candidate thread outputs. These may include:

- different names for the same underlying thread
- slightly different boundaries around the same thread
- some windows that create a `super_thread` where others do not
- late-emerging threads that only become clearly visible in later windows
- sub-threads that are real in some cases and over-fragmented in others

Your task is to consolidate these into the most useful year-wide catalogue.

## Core principles

### 1. Consolidate underlying threads, not labels
Do not preserve multiple canonical threads merely because the candidate labels differ.

If several window-level candidates clearly describe the same underlying recurring pattern, merge them.

Use:
- `source_candidate_ids`
- `source_candidate_names`
- `aliases`
- `merge_rationale`

to preserve provenance.

### 2. Prefer stable operational names
Choose canonical thread names that describe the recurring governing pattern clearly and durably.

Prefer names that are:
- specific enough to be meaningful
- broad enough to remain useful across many weeks
- operational rather than slogan-like
- suitable for year-level tracking and later weekly rewrite work

Do not simply copy the most recent or most dramatic window label if a better normalized name exists.

### 3. Do not over-create hierarchy
A `super_thread` should exist only when there are clearly multiple distinct child threads that remain genuinely useful when kept under an umbrella.

Do not create a `super_thread` merely because several threads feel related.

Prefer a strong `thread` unless the umbrella level is clearly necessary and likely to remain useful downstream.

### 4. Preserve real late-emerging threads
Some threads may only become legible in later windows.

Do not reject a thread merely because it is absent or underdeveloped in early windows if later windows show that it is genuinely distinct and recurring.

### 5. Distinguish true sub-threads from over-fragmentation
Use `sub_thread` only when:
- the narrower pattern is clearly distinct
- it would materially help later week-level tracking
- it is not just a more detailed phrasing of the parent thread

If a narrower label is just one operational arm of a broader thread, fold it into the broader thread instead of preserving it separately.

### 6. Preserve provenance and auditability
Every canonical thread must preserve traceability back to the window-level evidence.

Each canonical thread must record:
- which windows support it
- which weeks support it
- which source candidate IDs were merged into it
- which source candidate names contributed to it

### 7. Use Democracy Clock fields only as a mapping layer
The final canonical thread names should not be forced to match Democracy Clock categories or traits.

However, if a plausible mapping is clear, populate:
- `democracy_clock_categories`
- `democracy_clock_traits`

These are crosswalk fields, not naming constraints.

### 8. Reject weak or redundant candidates explicitly
When a window-level candidate should not survive into the final catalogue, record that in:
- `rejected_or_folded_candidates`

Use:
- `disposition = "folded"` when it has been merged into a canonical thread
- `disposition = "rejected"` when it is too weak, too local, too redundant, or otherwise not useful as a year-wide thread

## What makes a strong canonical thread

A strong canonical thread usually:
- appears across multiple windows
- is supported by multiple distinct weeks
- describes a recurring governing pattern rather than a topical bucket
- has stable meaning even when wording varies
- is useful for later weekly thread-status tracking and rewriting

## What does NOT deserve canonical status
These usually should be folded or rejected:
- one-off scandal framings
- near-duplicate labels that add no boundary distinction
- opportunistic umbrella labels with no real downstream value
- narrow labels that are better treated as one tactic within a broader recurring thread
- generic topical categories like "economy," "law," or "politics"

## Output requirements

Return **only** a valid JSON object.

Do **not** wrap it in markdown fences.
Do **not** include commentary before or after the JSON.
Do **not** explain your reasoning outside the JSON structure.

The JSON must conform to:

`phase1_consolidated_thread_catalog.schema.json`

## Output construction rules

### Required top-level fields
You must provide:
- `schema_name`
- `schema_version`
- `package_type`
- `scope`
- `build`
- `source_windows`
- `canonical_threads`
- `rejected_or_folded_candidates`
- `consolidation_notes`

### Canonical thread requirements
Each canonical thread must include:
- `thread_id`
- `canonical_name`
- `short_name`
- `description`
- `scope_level`
- `window_ids`
- `supporting_weeks`
- `source_candidate_ids`
- `source_candidate_names`
- `aliases`
- `inclusion_notes`
- `exclusion_notes`
- `boundary_notes`
- `parent_thread_id`
- `child_thread_ids`
- `related_thread_ids`
- `continuity_summary`
- `merge_rationale`
- `democracy_clock_categories`
- `democracy_clock_traits`

### Thread IDs
Use stable, uppercase IDs in this form:

`THR_SOMETHING_DESCRIPTIVE`

Examples:
- `THR_ADMIN_STATE_CAPTURE`
- `THR_IMMIGRATION_AS_CONTROL`
- `THR_INFORMATION_CONTROL_AND_MEMORY_REWRITING`

### On parent/child structure
- Use `parent_thread_id = null` when there is no parent
- Use `child_thread_ids = []` when there are no children
- Use `related_thread_ids` for genuine adjacency, not vague thematic similarity

### On supporting weeks
`supporting_weeks` should reflect distinct week numbers supported by the merged evidence, not repeated window appearances.

### On source candidate IDs and names
These fields should reflect the actual candidate provenance across windows. Preserve merge traceability.

### On continuity summary
This should summarize how the thread behaves across the year-level evidence:
- persistent from early windows
- late-emerging but clearly recurring
- broad and durable
- sharpened over time
- etc.

### On merge rationale
This should explain why the merged source candidates belong together and why the final canonical name and scope were chosen.

## Decision guidance

### When to keep a super-thread
Keep a `super_thread` only if:
- there are clearly distinct child threads beneath it
- the hierarchy adds real value
- the umbrella is likely to remain useful in later phases

### When to flatten hierarchy
Flatten to a single `thread` when:
- the supposed child threads are only different phrasings
- the umbrella adds no real analytical value
- the hierarchy would complicate week-level tracking without benefit

### When to keep a late-emerging thread
Keep it if:
- later windows clearly show recurrence and distinctiveness
- it is not merely one tactic of a broader thread
- it would plausibly matter in later status tracking and rewrites

### When in doubt
Prefer:
- one strong canonical thread over several near-duplicates
- one strong thread over an unnecessary super-thread
- explicit provenance over false precision

## Quality standard

The final catalogue should be stable enough to serve as the authoritative naming and boundary layer for later phases, including:
- week-level thread state
- dormant / reborn logic
- rewrite package generation
- thread-conscious weekly rewrites

The resulting catalogue should feel:
- coherent
- non-redundant
- traceable
- durable
- usable downstream

## Consolidation input package

The consolidation input package will be supplied below.

Use it as the full evidence base for this task.

---

{{CONSOLIDATION_INPUT_JSON}}