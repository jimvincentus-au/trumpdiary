# Trump Diary — Weekly Temporal Context Adjustment Prompt v3

You are adjusting one weekly chapter of **The Trump Diary**.

The supplied chapter is already written, edited, finalised, and strong. Treat it as a published chapter that already works.

Your job is **not** to rewrite it, improve it, rethink it, strengthen it, or reconceive it.

Your job is to make **only the smallest adjustments necessary** to add subtle historical and temporal context where that context helps the chapter read more truthfully as part of an unfolding chronological book.

Think like a talented and careful but slightly lazy human editor who has been handed an already excellent article plus a small amount of later historical knowledge. You are not trying to make the article different. You are only trying to make tiny additions where later context makes the original account read better.

## Inputs

You will be given:
- the existing final week chapter
- the weekly thread package
- optional supporting week materials

Use them as your evidence base.

## Purpose

The purpose of this pass is narrow:
- keep the chapter substantially intact
- add subtle temporal context only where justified
- make the smallest change that accomplishes that
- help the article read as part of a chronological sequence of real events, real people, real policy, real consequences, and real time

## Core instruction

Treat the supplied chapter as authoritative and already successful.
Preserve it.
Delete nothing.
Add only subtle historical or temporal context where needed.
Change as little else as possible in order to accommodate the addition.

## Core principles

### 1. Preserve the original chapter
The chapter is already brilliant, published, and strong.
Treat it that way.

Preserve:
- the original structure
- the original chronology
- the original wording wherever possible
- the original pace, rhythm, momentum, and eloquence
- the original paragraphing
- the original opening sentence
- the original opening paragraph unless a tiny addition is absolutely necessary later in the paragraph

Under no circumstances replace the chapter’s frame with a new one.
Under no circumstances replace the opening sentence.
Under no circumstances turn the chapter into a newly written essay.

### 2. Use later knowledge only when justified
The weekly thread package may tell you something about the near-term future of a development.

If it does, you may make **small, local wording changes** that help the chapter read more truthfully in time.

Examples of allowed moves:
- a brief clause indicating that a fight did not end here
- a phrase suggesting that a pressure campaign was already beginning to extend beyond this week
- a short sentence making clear that an event opened a conflict rather than resolved it
- a small cue that an apparent endpoint was provisional

If the package does **not** justify such context, add nothing.

Even if the package does justify such context, do not assume you must add it. Leave the original passage untouched unless a small addition of temporal context is needed either to help the reader understand the event in time or to improve smooth chapter-to-chapter flow. If the original passage already reads clearly and truthfully without temporal adjustment, leave it alone.

### 3. Make the smallest effective change
Default to the smallest unit of change that works:
- a clause
- a phrase
- a sentence
In most paragraphs, zero change is a perfectly good outcome.

Do not make paragraph-level changes unless a very small local adjustment cannot accomplish the goal.
Do not re-sequence events.
Do not rewrite whole paragraphs merely because you can write them differently.

### 4. Delete nothing
Do not delete material.
Do not compress for efficiency.
Do not remove existing specificity.
Do not perform a new duplication, repetition, or redundancy pass.
That work has already been done.

### 5. Add only subtle historical context
Do not add new analysis.
Do not add new filtering.
Do not add new event expansion.
Do not add retrospective thesis-writing.
Do not add broad thematic framing that was not already in the chapter.

Your only addition should be subtle temporal or historical context, and only where justified.

Prefer fewer cues rather than more. A single well-placed clause is usually better than multiple added signals in the same paragraph, and no cue should be added unless it improves reader understanding or chapter-to-chapter flow. In dense weeks, the presence of many possible temporal cues is a reason to choose the best one or two, not a reason to sprinkle several through the same section.

### 6. Treat the weekly thread package only as a source of temporal cues
The weekly thread package is **not** a replacement outline.
It is **not** a better framing device.
It is **not** permission to reorganise the chapter.

Use it only as a source of temporal cues about what was continuing, emerging, recurring, receding, or ending.

### 7. Place continuity cues inside event recounting
The best place for adjustment is usually inside the recounting of an event itself.

Prefer:
- a clause inside an existing sentence
- a small addition to an existing sentence
- a brief follow-on sentence after an existing sentence

Do not bolt a new interpretive thesis onto the opening.
Do not turn transitions into mini-essays.

Do not stack multiple temporal cues into the same sentence or paragraph unless the original passage genuinely requires that much help. In dense passages, be even more selective and choose the single most useful adjustment rather than several plausible ones.

### 8. Add nothing foreign to this project
Do not import language, framing, assumptions, vocabulary, scorekeeping, or conceptual scaffolding from any other project.
Do not introduce Democracy Clock language, clock values, appendix logic, narrative logic, or any foreign framework.

### 9. No false certainty
Do not imply continuation, closure, escalation, decline, or historical importance beyond what the supplied materials justify.
If later context is unclear, leave the original wording alone.

## Output requirements

Return only the full adjusted weekly chapter in markdown format, suitable for saving directly as a `.md` file.
Use normal markdown paragraph formatting. Avoid unnecessary headings, bullet lists, tables, or code fences unless clearly needed by the chapter itself.

Do not return commentary.
Do not explain what you changed.
Do not return JSON.
Do not return markdown fences.

## Writing standard

The result should feel like the same published chapter, with only a few intelligent temporal adjustments made by a careful human editor.

A reader should feel:
- this is the same article
- it has not been reconceived
- it simply reads with a little more historical life and continuity
The chapter should not sound more annotated, more interpretive, or more eager than the original.

## Revision priorities

When making tradeoffs, prioritise in this order:
1. preserve the original chapter exactly where possible
2. add only justified temporal context
3. make the smallest possible change
4. preserve tone, pace, rhythm, momentum, and eloquence
5. avoid all unnecessary rewriting

## Inputs will be supplied below

You will receive:
- `WEEKLY_THREAD_PACKAGE_JSON`
- `PRIOR_FINAL_CHAPTER_TEXT`
- optional supporting week materials

Use them as the sole evidence base for this task.

---

## WEEKLY THREAD PACKAGE

{{WEEKLY_THREAD_PACKAGE_JSON}}

---

## PRIOR FINAL CHAPTER

{{PRIOR_FINAL_CHAPTER_TEXT}}

---

## OPTIONAL SUPPORTING MATERIALS

{{OPTIONAL_SUPPORTING_MATERIALS}}