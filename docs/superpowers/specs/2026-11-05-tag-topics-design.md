# tag-topics: what a file is about

Agreed in chat on 2026-11-05.

## Problem

`tag-visuals` sends only frames and asks only for what is visible (object, scene,
activity, attribute). It never says what a video is about. A study-abroad agency's
student success story comes back as `person`, `speaking-to-camera`, `certificate`, with
nothing saying "student testimonial about an Australian student visa". The meaning is
mostly in the speech, which `transcribe` already captures, but nothing combines the two.

## Decisions

1. **New processor `tag-topics`.** It runs after `transcribe` and `tag-visuals` and reads
   their results for the same source file (same `<name>-<hash8>`). One of the two is
   enough: a silent video or a photo has only visual tags.
2. **Transcript, not audio.** ElevenLabs has already been paid for the speech, text is
   far cheaper than audio, and OpenAI stays on its approved route (`lib/openai_api.py`).
3. **One text-only OpenAI request per file.** No images. It runs after the other two
   processors, not alongside them, because it reads their results. Frame tagging never
   sees the transcript, so visual tags stay pure perception.
4. **Model:** `OPENAI_TOPIC_MODEL`, defaulting to the tagging model
   (`OPENAI_VISION_MODEL`). **Reasoning effort:** `OPENAI_TOPIC_REASONING_EFFORT`,
   default `low` (frame tagging uses `none`).
5. **Output categories:** `type` (kind of media), `topic` (what it is about), `entity`
   (named things that are not people: countries, schools, organisations, programmes, visa
   subclasses). `topics.json` also carries `visual` (the file's visual tag labels, copied
   from `tags.json`, which is not changed) and a `summary` of at most 40 words.
6. **Evidence:** every tag cites references into the material it was given: speech sentences
   `S1, S2, ...` (with their part's times and their number in it; the transcript has no finer times), on-screen texts `T1, T2, ...`, visual tags
   `V:<label>`. Tags whose references don't exist are dropped.
7. **No personal names**, in tags or in the summary, even when spoken or shown. People are
   referred to by role ("the student").
8. **Tag format, for all tags (visual and topic):** English, lowercase, words joined by
   hyphens (`speaking-to-camera`, `subclass-500`). One helper (`lib/tags.py`) normalises
   every label, including those in results saved before this rule, without rewriting
   those results.
9. **Library:** topic tags already used in `output/tag-topics/*/topics.json` are offered
   for reuse, like the visual tag library; tags new to it are marked `new`.
10. **Pipeline:** `/process-video` runs `tag-topics` after both processors finish.

## Example result

```json
{
  "visual": ["office", "speaking-to-camera", "certificate"],
  "type": ["student-testimonial"],
  "topic": ["australia-student-visa", "visa-success-story"],
  "entity": ["australia", "subclass-500"],
  "summary": "A student describes getting an Australian student visa through the agency.",
  "tags": [
    { "label": "subclass-500", "category": "entity", "confidence": "high", "new": true,
      "evidence": [{ "ref": "S1", "source": "speech", "start_seconds": 0, "end_seconds": 120 }] }
  ]
}
```
