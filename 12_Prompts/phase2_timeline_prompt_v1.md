# Trump Chronicles — Timeline by Week Prompt v1

You are generating the back-matter appendix **Timeline by Week** for the book **Trump Chronicles**.

The appendix is a reader-friendly chronology, not a full event log, not a marketing synopsis, and not an academic index.

Your job is to convert one week’s source materials into one compact, disciplined timeline entry that helps a reader relocate the week and understand why it mattered.

## Inputs

You will be given:
- the weekly metadata stack for each included week
- the weekly spine for each included week

Use them as your evidence base.

## Purpose

The purpose of this pass is narrow:
- create a clean back-matter appendix covering the included weeks
- preserve each week’s main democratic significance
- compress rather than expand
- help the appendix function as a navigational map of the full 53-week book

## Core instruction

Generate the full timeline appendix output for the supplied weeks.
Return valid JSON only.
Return a single top-level object matching the timeline output schema.
Do not return commentary, explanation, or markdown fences.
Do not invent facts not supported by the supplied materials.

## Core principles

### 1. Treat the supplied materials as authoritative
Use the metadata stack and weekly spine as the sole evidence base.
Do not import facts, framing, or interpretation from outside the supplied materials.

### 2. The timeline entry must be compact
This appendix is for scanability and relocation.
Do not produce mini-summaries, lists of events, or paragraphs of analysis.

### 3. Use the metadata title as the basis for each chapter title
Use the metadata title as the basis for each `chapter_title`.
Remove the boilerplate prefix `This Week in Democracy:` if present.
Do not add new title language.

### 4. The gloss must be exactly one sentence
Each gloss must be one sentence only.
Each gloss should usually be 22–38 words.
Each gloss should identify the week’s main democratic significance, not provide a laundry list.
Prefer structural language over rhetorical flourish.

### 5. Preserve the right level of abstraction
The gloss should help the reader remember what changed, escalated, was tested, or became visible in that week.
It should not try to capture every front of activity.
Usually it should name:
- the week’s main governing mechanism, shift, or conflict
- the main democratic domain or domains involved
- meaningful pushback, resistance, or constraint, if that was an important part of the week

### 6. Do not simply reuse long source text verbatim
Compress from the source materials.
Do not paste the long synopsis or week summary unchanged.
The final gloss should read like appendix prose, not chapter metadata.

### 7. Follow source priority for the gloss
Use this priority order when selecting source material for the gloss:
1. `metadata.week_summary`
2. `metadata.short_synopsis`
3. `spine.week_summary`
4. `metadata.long_synopsis`
5. `whole_week_arcs`

If the higher-priority field is present and usable, prefer it.
Only fall back when needed.

### 8. No false precision or false drama
Do not exaggerate.
Do not add rhetorical heat.
Do not imply significance beyond what the supplied materials justify.
Do not claim resolution, continuation, or turning-point status unless the materials support it.

## Output requirements

Return one JSON object only, matching the full timeline output schema.

Required top-level shape:

{
  "schema_name": "phase2_timeline_output",
  "schema_version": "1.0",
  "section": "timeline_by_week",
  "book_title": "Trump Chronicles",
  "generated_from": {
    "metadata_stack": "string",
    "weekly_spine": "string"
  },
  "entries": [
    {
      "week": integer,
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD",
      "date_display": "Month D–D, YYYY",
      "chapter_title": "string",
      "gloss": "string",
      "source_priority_used": "string"
    }
  ]
}

## Writing standard

The result should feel disciplined, compact, and useful in print.
A reader scanning the full set of entries should be able to relocate any week quickly and understand its main democratic significance without rereading the chapter.

## Revision priorities

When making tradeoffs, prioritise in this order:
1. factual fidelity to the supplied materials
2. compactness and scanability
3. clear statement of each week’s main democratic significance
4. consistency of format across weeks
5. restrained, reader-friendly prose

## Inputs will be supplied below

You will receive:
- `GENERATED_FROM_JSON`
- `WEEKLY_INPUTS_JSON`

Use them as the sole evidence base for this task.

---

## GENERATED FROM

{{GENERATED_FROM_JSON}}

---

## WEEKLY INPUTS

{{WEEKLY_INPUTS_JSON}}