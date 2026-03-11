# Trump Diary — Weekly Thread Package Prompt v1

You are creating a **week-level thread-state package** for **The Trump Diary**.

Your task is to read:
- the canonical thread catalogue
- the current week’s source materials
- the prior week’s thread package if provided

and produce a JSON object that conforms to:

`weekly_thread_package.schema.json`

## Purpose

This package is the control layer between the **year-wide canonical thread catalogue** and the **thread-conscious rewrite pass** for each week.

Your job is to determine, for the current week:

- which canonical threads are present
- which are primary, secondary, background, or absent-but-relevant
- whether each thread is new, continuing, dormant, reborn, or inactive
- what evidence in the week supports that judgment
- what the rewrite pass should emphasize, downplay, mention briefly, or omit

## Core principles

### 1. Use only canonical thread IDs and names
Do not invent new thread IDs.
Do not rename canonical threads.
Do not create new year-level ontology in this step.

Use the supplied catalogue as the authority for:
- `thread_id`
- `canonical_name`
- `scope_level`

### 2. Think week-level, not year-level
The catalogue defines the thread.
This step determines the thread’s **state in the current week**.

You are not re-deciding whether the thread exists in the year.
You are deciding how it functions **this week**.

### 3. Status values
Use these status values carefully:

- `new`  
  Use when the thread appears meaningfully for the first time in the current week, based on the supplied prior-week context.

- `continuing`  
  Use when the thread is clearly active this week and is carrying forward from prior recent weeks.

- `dormant`  
  Use when the thread is not actively developed this week but remains meaningfully part of the ongoing backdrop and should still shape the rewrite context.

- `reborn`  
  Use when the thread had previously gone quiet or materially receded and is now clearly active again.

- `inactive`  
  Use when the thread is not meaningfully part of the current week and should not shape the rewrite except perhaps by omission logic.

Do not use these mechanically. Use them narratively but consistently.

### 4. Presence and role are not identical
A thread may be:
- present but only background
- absent in direct events but still relevant context
- highly present and clearly primary

So determine both:
- `is_present`
- `week_role`

### 5. Salience is about narrative weight
Use:
- `high`
- `medium`
- `low`

This should reflect how central the thread is to understanding the week, not merely whether one source mentions it.

### 6. Evidence must be specific
Each thread state must include `evidence_items` tied to actual supplied materials.

Use evidence from:
- development allocator
- digest
- event log
- week markdown
- other supplied week materials

Each evidence item must explain **why it matters** for the thread.

### 7. Rewrite guidance must be practical
Your output is meant to drive a rewrite.

So `rewrite_guidance` must help a later writer decide:
- what leads the week
- what supports the lead
- what stays in the background
- what should be omitted
- what continuity should be emphasized from prior weeks

### 8. Do not overload the week
Not every canonical thread needs heavy treatment every week.

Prefer:
- a small number of lead threads
- a manageable support structure
- clear omission/downplay decisions

### 9. Use prior-week context when available
If a prior week thread package is supplied, use it to help determine:
- continuing
- dormant
- reborn
- carry-forward logic

If there is no prior-week package, use `null` or cautious judgments where appropriate.

### 10. Keep hierarchy subordinate to weekly clarity
If a super-thread and one of its child threads are both relevant, choose the level that best helps the weekly rewrite.

Do not automatically privilege the umbrella level.
Do not automatically privilege the child level.
Choose the level or mix that best explains the week.

## Output requirements

Return **only** a valid JSON object.

Do **not** wrap it in markdown fences.
Do **not** include commentary before or after the JSON.
Do **not** explain your reasoning outside the JSON structure.

The JSON must conform to:

`weekly_thread_package.schema.json`

## Output construction rules

### Required top-level fields
You must provide:
- `schema_name`
- `schema_version`
- `package_type`
- `scope`
- `build`
- `catalog_reference`
- `sources`
- `week`
- `thread_states`
- `week_summary_notes`
- `rewrite_guidance`

### Thread state requirements
Each `thread_state` must include:
- `thread_id`
- `canonical_name`
- `scope_level`
- `status`
- `salience`
- `week_role`
- `is_present`
- `carry_forward_from_prior_week`
- `evidence_items`
- `summary`
- `continuity_notes`
- `rewrite_priority`
- `recommended_paragraph_weight`

### Rewrite priority
Use:
- `lead`
- `major`
- `supporting`
- `mention_only`
- `omit`

Interpretation:
- `lead` = one of the main drivers of the week
- `major` = clearly important but not the principal frame
- `supporting` = should appear, but not dominate
- `mention_only` = brief reference at most
- `omit` = not worth carrying into the rewrite

### Recommended paragraph weight
This is an integer estimate of likely paragraph emphasis.

Guidance:
- `0` = omit
- `1` = mention briefly
- `2` = modest support
- `3` = major support
- `4+` = lead/anchor thread

This is guidance, not a rigid quota.

### Week summary notes
Use these to capture high-level observations about the week, such as:
- dominant thread collisions
- major escalations
- unusually thin continuity
- shifts in emphasis
- whether the week should be framed through one dominant thread or multiple intersecting ones

### Rewrite guidance
This should be directly useful to the weekly rewrite pass.

Populate:
- `lead_threads`
- `supporting_threads`
- `background_threads`
- `threads_to_downplay`
- `threads_to_omit`
- `opening_focus`
- `closing_focus`
- `continuity_emphasis_notes`

## Decision guidance

### When to mark a thread as primary
Use `week_role = primary` when the thread is one of the central explanatory frames of the week.

### When to mark a thread as absent_but_relevant
Use this when the thread is not directly developed by fresh major evidence in the week, but still matters as context for interpreting the week’s events.

### When to mark a thread as dormant
Use `dormant` when the thread should remain in memory but not in the foreground.

### When to mark a thread as reborn
Use `reborn` only when there is a real reactivation after a quieter period, not just another week of continuation.

### When in doubt
Prefer:
- fewer lead threads
- clearer evidence
- practical rewrite value
- continuity notes that help downstream writing

## Quality standard

The package should be strong enough that a later rewrite step can use it, together with the week’s prior final markdown, to produce a more thread-conscious weekly chapter without having to rediscover the week’s structure.

It should feel:
- specific
- disciplined
- narratively useful
- faithful to the canonical catalogue
- grounded in actual weekly evidence

## Inputs

The input package for this task will be supplied below.

Use it as the full evidence base for this week.

---

{{WEEKLY_THREAD_INPUT_JSON}}