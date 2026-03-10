# Trump Diary — Phase 1 Discovery Prompt v1

You are identifying **candidate continuity threads** from one overlapping discovery window of weekly development allocator files for **The Trump Diary**.

Your task is to read the supplied window package and produce a JSON object that conforms to the schema:

`phase1_candidate_threads.schema.json`

## Purpose

This is **Phase 1 thread discovery**, not final catalogue construction and not week-by-week status adjudication.

You are working on **one overlapping window** of weeks. Your job is to identify the main recurring continuity threads visible **within this window**.

A continuity thread is a recurring governing pattern, institutional campaign, policy arc, or method of democratic erosion that appears across multiple weeks in the supplied window.

You are **not** assigning:
- weekly status values such as `new`, `continuing`, `dormant`, or `reborn`
- weekly intensities
- final year-wide thread IDs
- final merge decisions across all windows

You **are** identifying:
- candidate continuity threads visible in this window
- the weeks that support each thread
- the specific development items that support each thread
- aliases and variant phrasings
- boundary notes that help later consolidation

## Core principles

### 1. Think in threads, not topics
A thread is not just a subject area like "immigration" or "courts."

A good thread has a coherent underlying pattern or method, such as:
- administrative state capture via DOGE and civil-service purge
- immigration and citizenship as tools of tiered belonging and dissent control
- public-record erasure and information control
- law as protection for allies and punishment for opponents

Avoid labels that are so broad that they are always present somewhere.

### 2. Prefer the right level of abstraction
Do not explode the output into dozens of tiny one-off subtopics.
Do not collapse everything into a few vague mega-topics.

Aim for durable, meaningful continuity threads that could plausibly recur across many weeks of the year.

Use these scope levels:
- `super_thread` for a broad umbrella containing multiple distinct but related threads
- `thread` for the preferred default level
- `sub_thread` only when the narrower pattern is clearly distinct and useful

### 3. Use the supplied development allocator material faithfully
Ground every candidate thread in the actual supplied weekly development allocator content.

Every candidate thread must have:
- `supporting_weeks`
- `supporting_developments`

Use the actual development titles and, if available, development IDs from the source material.

### 4. Be window-local but year-aware in style
You are only deciding what is visible **in this window**.
You may describe a thread as `emergent`, `recurring`, `sustained`, or `unclear` within this window.

Do not pretend to know the whole year from this one window.

### 5. Be careful with boundaries
Distinguish adjacent but non-identical threads when useful.

For example:
- "administrative state capture" is not the same as "private-state fusion," though they may be related
- "immigration as domestic control" is not identical to "election administration interference," even if they overlap in some weeks

Use:
- `boundary_notes`
- `related_candidate_ids`
- `possible_parent_candidate_id`
- `possible_child_candidate_ids`
when helpful

### 6. Reject weak or purely local labels
Do not create a candidate thread if it is:
- only a one-week event with no real continuity
- too narrow to matter for year-level consolidation
- merely a generic topic heading
- redundant with a stronger candidate

Use `rejected_or_folded_candidates` for weak, duplicate, or folded labels.

## What counts as a candidate continuity thread

A candidate continuity thread usually has several of these characteristics:
- appears in multiple weeks within the window
- reflects an ongoing governing method, campaign, or institutional pressure
- can be described in a way that would still make sense outside one single week
- has enough coherence to be consolidated later with similar candidates from other windows

## What does NOT count well
These are usually poor thread candidates unless clearly part of something larger:
- one-off scandal headlines
- isolated speeches with no recurring pattern
- generic labels like "economy," "law," "politics," "rights"
- temporary framing language unique to one week

## Output requirements

Return **only** a valid JSON object.

Do **not** wrap it in markdown fences.
Do **not** include commentary before or after the JSON.
Do **not** explain your reasoning outside the JSON structure.

The JSON must conform to the schema:
`phase1_candidate_threads.schema.json`

## Output construction rules

### Required top-level fields
You must provide:
- `schema_name`
- `schema_version`
- `package_type`
- `source_window`
- `build`
- `candidate_threads`

### Candidate thread requirements
Each candidate thread must include:
- `candidate_id`
- `canonical_name`
- `short_name`
- `description`
- `scope_level`
- `supporting_weeks`
- `supporting_developments`
- `aliases`
- `inclusion_notes`
- `boundary_notes`

### Candidate IDs
Use stable, uppercase, descriptive candidate IDs in this form:

`cand_SOMETHING_DESCRIPTIVE`

Examples:
- `cand_ADMIN_STATE_CAPTURE`
- `cand_IMMIGRATION_AS_CONTROL`
- `cand_INFO_CONTROL_AND_RECORD_ERASURE`

### Supporting developments
For each supporting development:
- include the correct `week_number`
- include `development_title`
- include `development_id` if present in the source
- assign `role` as one of:
  - `primary`
  - `secondary`
  - `contextual`
- briefly explain `why_it_supports_thread`

### Aliases
Use aliases to capture variant phrasings found in the weekly allocator language.

### Inclusion and exclusion
Use `inclusion_notes` to clarify what belongs in the thread.
Use `exclusion_notes` when needed to clarify what should stay out.

### Continuity assessment
Use one of:
- `emergent`
- `recurring`
- `sustained`
- `unclear`

Interpret these only within the supplied window.

## Decision guidance

### When to create a super-thread
Create a `super_thread` only when there are clearly multiple distinct thread candidates beneath it.
Do not create a `super_thread` merely because several developments feel related; prefer a strong `thread` unless the umbrella level is clearly necessary and likely to remain useful at year-level consolidation.

### When to create a sub-thread
Create a `sub_thread` only when the narrower recurring pattern is distinct enough that later consolidation would benefit from preserving it separately.

### When in doubt
Prefer a strong `thread` with good boundary notes over unnecessary hierarchy.

## Quality standard

The output should help a later consolidation step answer:
- which candidate threads are genuinely recurring across windows
- which labels should merge
- which candidates are too broad
- which candidates are too narrow
- which candidate names best represent the underlying continuity

## Source window package

The window package will be supplied below.

Use it as the sole evidence base for this task.

---

{{WINDOW_PACKAGE_JSON}}