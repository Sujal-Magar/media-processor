# tag-topics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `tag-topics` processor that tags what a file is about (type, topic, entity) from its transcript, visual tags and on-screen text, and switch every tag in the repo to English, lowercase and hyphen-joined.

**Architecture:** A shared `lib/tags.py` cleans tag labels and rebuilds a processor's tag library from its results. `tag-visuals` adopts it. The new processor follows the repo's three-script pattern: `prepare.py` (free) reads `output/transcribe/<name>-<hash8>/transcript.json` and `output/tag-visuals/<name>-<hash8>/tags.json` and builds the text to send, `tag.py` sends one text-only OpenAI request (paid), and `finalize.py` writes `topics.md`/`topics.json`/`metadata.json`. `/process-video` runs it after both processors finish.

**Tech Stack:** Python 3.10+ standard library only, `lib/openai_api.py` (OpenAI Responses API with strict JSON schema), `unittest` for tests (pytest is not installed).

**Spec:** `docs/superpowers/specs/2026-11-05-tag-topics-design.md`

## Global Constraints

- Every tag, visual or topic, is English, lowercase, with words joined by hyphens (`speaking-to-camera`, `subclass-500`). Labels are cleaned only through `lib.tags.clean_label`.
- Standard library only. No new dependencies. Tests use `unittest`, always run from the repo root as `python3 -m unittest discover -s tests -v`.
- Never run a paid step while implementing: neither `processors/*/tag.py` against a real job nor `mcp__elevenlabs__speech_to_text`. Tests mock `request`.
- Do not open files in `output/` or `work/`. Never read `.env`.
- Never rewrite existing results in `output/`. Results saved with spaced labels are cleaned when read.
- Scripts print only counts, statuses and paths, never tags, text or transcript.
- Topic tags and the summary never contain a person's name; people are referred to by role.
- **Do not run `git commit`.** The user commits. Each task ends by handing over a minimal one-line commit message.
- Match the surrounding code: `from __future__ import annotations`, the `sys.path.insert(0, ...)  # repo root, for \`lib\`` line in scripts, docstrings that explain *why*, `# fmt: skip` on hand-formatted calls.

## Review Focus

- A library holding both old spaced tags (`speaking to camera`) and new hyphenated ones must count them as one tag with merged uses, never two. (Task 1 test `test_old_spaced_and_new_hyphenated_tags_merge`)
- Re-running `/transcribe` or `/tag-visuals` with `force` (or adding the missing one) after topics were made must make `prepare` report `outdated`, not `already_done`. (Task 5 test `test_previous_status_outdated_when_inputs_change`)
- A photo or a silent video has no transcript, so a model answer citing `S1` there must not keep that evidence; a tag left with none is dropped. (Task 3 test `test_refs_not_sent_are_dropped`)
- The model returning `Visa Success Story` and `visa-success-story` in one answer must give one hyphenated tag with both tags' evidence. (Task 3 test `test_labels_cleaned_and_repeats_merged`)
- Running `tag.py` again after the request succeeded but before finalize finished must send nothing (no second charge). (Task 4 test `test_saved_answer_is_not_sent_again`)

---

### Task 1: Shared tag wording and tag library (`lib/tags.py`) and the test setup

**Files:**
- Create: `lib/tags.py`
- Create: `tests/helpers.py`
- Create: `tests/test_tags.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `lib.tags.clean_label(label: str) -> str`
  - `lib.tags.tag_library(folder: Path, result_file: str, exclude: Path | None, limit: int) -> list[dict]`, where each item is `{"label": str, "category": str, "uses": int}`, most used first
  - `tests/helpers.py`: `ROOT: Path` (repo root, put on `sys.path`) and `load_script(processor: str, name: str) -> ModuleType`

- [ ] **Step 1: Write the test helper**

`tests/helpers.py`:

```python
"""Shared test setup: the repo root on sys.path, and loading processor scripts."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCRIPT_NAMES = ("prepare", "tag", "finalize")


def load_script(processor: str, name: str) -> ModuleType:
    """processors/<processor>/<name>.py as a fresh module. The scripts import each other
    by bare name (`from finalize import ...`), so those names are cleared first, or one
    processor's finalize would stand in for another's."""
    folder = ROOT / "processors" / processor
    for script in SCRIPT_NAMES:
        sys.modules.pop(script, None)
    sys.path.insert(0, str(folder))
    try:
        spec = importlib.util.spec_from_file_location(
            f"{processor.replace('-', '_')}_{name}", folder / f"{name}.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(folder))
    return module
```

- [ ] **Step 2: Write the failing tests**

`tests/test_tags.py`:

```python
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  (repo root on sys.path)

from lib.tags import clean_label, tag_library


class CleanLabelTest(unittest.TestCase):
    def test_spaces_and_case_become_hyphens(self):
        self.assertEqual(clean_label("  Speaking  to Camera "), "speaking-to-camera")

    def test_underscores_and_repeated_hyphens(self):
        self.assertEqual(clean_label("subclass__500 -- visa"), "subclass-500-visa")

    def test_existing_hyphens_kept(self):
        self.assertEqual(clean_label("close-up"), "close-up")

    def test_only_separators_is_empty(self):
        self.assertEqual(clean_label(" - _ "), "")


class TagLibraryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def write(self, name: str, tags: list[dict], file: str = "tags.json") -> Path:
        result = self.folder / name
        result.mkdir()
        (result / file).write_text(json.dumps({"tags": tags}), encoding="utf-8")
        return result

    def test_old_spaced_and_new_hyphenated_tags_merge(self):
        self.write("a-11111111", [{"label": "speaking to camera", "category": "activity", "frames": [0, 1]}])
        self.write("b-22222222", [{"label": "speaking-to-camera", "category": "activity", "frames": [3]}])
        self.assertEqual(
            tag_library(self.folder, "tags.json", None, 10),
            [{"label": "speaking-to-camera", "category": "activity", "uses": 3}],
        )

    def test_excluded_folder_and_broken_files_skipped(self):
        own = self.write("a-11111111", [{"label": "office", "category": "scene", "frames": [0]}])
        broken = self.folder / "b-22222222"
        broken.mkdir()
        (broken / "tags.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(tag_library(self.folder, "tags.json", own, 10), [])

    def test_result_without_frames_counts_once(self):
        self.write("a-11111111", [{"label": "Australia", "category": "entity"}], "topics.json")
        self.write("b-22222222", [{"label": "australia", "category": "entity"}], "topics.json")
        self.assertEqual(
            tag_library(self.folder, "topics.json", None, 10),
            [{"label": "australia", "category": "entity", "uses": 2}],
        )

    def test_limit_keeps_most_used(self):
        self.write("a-11111111", [
            {"label": "office", "category": "scene", "frames": [0, 1, 2]},
            {"label": "laptop", "category": "object", "frames": [0]},
        ])  # fmt: skip
        self.assertEqual(
            [t["label"] for t in tag_library(self.folder, "tags.json", None, 1)],
            ["office"],
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'lib.tags'`

- [ ] **Step 4: Write `lib/tags.py`**

```python
"""Tag wording and tag libraries shared by the tagging processors.

Every tag is stored in English, lowercase, with its words joined by hyphens
("speaking-to-camera", "subclass-500"). A processor's library is rebuilt from its
earlier results on every run, so it never drifts from what is on disk.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


def clean_label(label: str) -> str:
    """A tag as stored: lowercase, each run of spaces, underscores and hyphens made one
    hyphen, none at either end. Results saved before hyphens ("speaking to camera")
    read the same as new ones."""
    return "-".join(re.split(r"[\s_-]+", label.strip().lower())).strip("-")


def tag_library(
    folder: Path, result_file: str, exclude: Path | None, limit: int
) -> list[dict]:
    """The vocabulary of one processor's results: each {label, category} in the `tags`
    of folder/*/<result_file>, with how often it was used (its frames, or 1 for a tag
    without frames), most used first.

    `exclude` is the source file's own result folder: when redoing it with --force, its
    old tags must not count as the library, or nothing would ever be marked new.
    """
    uses: Counter[tuple[str, str]] = Counter()
    for path in folder.glob(f"*/{result_file}"):
        if path.parent == exclude:
            continue
        try:
            tags = json.loads(path.read_text(encoding="utf-8")).get("tags", [])
        except (OSError, ValueError):
            continue
        for tag in tags:
            label = clean_label(str(tag.get("label") or ""))
            if label and tag.get("category"):
                uses[(label, tag["category"])] += len(tag.get("frames") or [0])
    return [
        {"label": label, "category": category, "uses": count}
        for (label, category), count in uses.most_common(limit)
    ]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: 8 tests, OK

- [ ] **Step 6: Hand over for commit (do not commit)**

Tell the user the files changed and the message: `feat: add shared tag cleaning and tag library`

---

### Task 2: tag-visuals writes hyphenated tags

**Files:**
- Modify: `processors/tag-visuals/finalize.py` (remove local `clean_label` near line 50; per-frame tags in `finalize()`; document `version`)
- Modify: `processors/tag-visuals/prepare.py` (`existing_tags`, `previous_tags`, imports)
- Modify: `processors/tag-visuals/tag.py` (`INSTRUCTIONS` lines 85-109, `earlier_batches_text` line 210)
- Modify: `.claude/skills/tag-visuals/SKILL.md` (last paragraph)
- Modify: `CLAUDE.md` (layout table, visual tags paragraph)
- Modify: `README.md` (Layout block)
- Test: `tests/test_tag_visuals_labels.py`

**Interfaces:**
- Consumes: `lib.tags.clean_label`, `lib.tags.tag_library`, `tests/helpers.load_script`
- Produces: `tags.json` version 3, with hyphenated labels in `tags` and in each frame's `tags`. Nothing else changes shape.

- [ ] **Step 1: Write the failing tests**

`tests/test_tag_visuals_labels.py`:

```python
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from helpers import load_script

finalize = load_script("tag-visuals", "finalize")
tag = load_script("tag-visuals", "tag")
prepare = load_script("tag-visuals", "prepare")


class TagVisualsLabelsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.dir = Path(temporary.name)

    def test_aggregate_hyphenates_and_matches_old_library_tags(self):
        plan = {
            "frames": [
                {"index": 0, "time_seconds": 0.0, "file": "a.jpg"},
                {"index": 1, "time_seconds": 5.0, "file": "b.jpg"},
            ],
            "source": {"duration_seconds": 10.0},
            "existing_tags": [{"label": "speaking to camera", "category": "activity"}],
        }
        tagged = {
            0: {"tags": [{"label": "Speaking to camera", "category": "activity", "confidence": "high"}]},
            1: {"tags": [{"label": "speaking-to-camera", "category": "activity", "confidence": "medium"}]},
        }
        [entry] = finalize.aggregate(plan, tagged)
        self.assertEqual(entry["label"], "speaking-to-camera")
        self.assertFalse(entry["new"])
        self.assertEqual(entry["frames"], [0, 1])

    def test_earlier_batches_offer_hyphenated_tags(self):
        (self.dir / "batch_000.json").write_text(json.dumps({"frames": [
            {"index": 0, "tags": [{"label": "White Shirt", "category": "object", "confidence": "high"}],
             "on_screen_text": []},
        ]}), encoding="utf-8")  # fmt: skip
        text = tag.earlier_batches_text(self.dir, [{"index": 1}])
        self.assertIn("object: white-shirt", text)

    def test_instructions_ask_for_hyphens(self):
        self.assertIn("speaking-to-camera", tag.INSTRUCTIONS)
        self.assertNotIn("speaking to camera", tag.INSTRUCTIONS)
        self.assertIn("joined by hyphens", tag.INSTRUCTIONS)

    def test_previous_tags_hyphenated_and_known_dropped(self):
        (self.dir / "tags.json").write_text(json.dumps({"tags": [
            {"label": "White Shirt", "category": "object", "frames": [0]},
            {"label": "white shirt", "category": "object", "frames": [2]},
            {"label": "office", "category": "scene", "frames": [0, 1]},
        ]}), encoding="utf-8")  # fmt: skip
        existing = [{"label": "office", "category": "scene", "uses": 2}]
        self.assertEqual(
            prepare.previous_tags(self.dir, existing),
            [{"label": "white-shirt", "category": "object", "uses": 2}],
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: the 4 new tests fail. For example, `aggregate` returns `speaking to camera`, and `earlier_batches_text` contains `white shirt`. The 8 tests from Task 1 still pass.

- [ ] **Step 3: `finalize.py`: use the shared `clean_label`**

Delete the local function:

```python
def clean_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip().lower())
```

and add the import below the `lib.workspace` import block:

```python
from lib.tags import clean_label
```

`re` is still used by `clean_text`, so keep `import re`.

In `finalize()`, store each frame's tags with clean labels. Replace:

```python
                "tags": result.get("tags", []),
```

with:

```python
                "tags": [
                    {**tag, "label": clean_label(tag["label"])}
                    for tag in result.get("tags", [])
                ],
```

Bump the document version and its comment. Replace:

```python
        # 2: text items are {text, legibility, detail}, plus `confirmed: false` on pass-1
        # text a re-read of the frame did not read again; text_pass.status
        "version": 2,
```

with:

```python
        # 2: text items are {text, legibility, detail}, plus `confirmed: false` on pass-1
        # text a re-read of the frame did not read again; text_pass.status
        # 3: tag labels joined by hyphens (lib/tags.py)
        "version": 3,
```

Run `grep -rn "clean_label" processors/` to confirm nothing else imported the removed function from `finalize`.

- [ ] **Step 4: `tag.py`: ask for hyphens and offer clean earlier tags**

In `INSTRUCTIONS`, replace these lines:

```
For every frame, list what is clearly visible as short lowercase English tags:
- object: physical things (person, laptop, microphone, car, dog)
- scene: the setting (office, classroom, street, kitchen, outdoors, stage)
- activity: what people are doing (presenting, typing, walking, cooking); use
  "speaking to camera" when a person visibly talks to the camera
- attribute: visual qualities (night, close-up, crowded, text on screen)
```

with:

```
For every frame, list what is clearly visible as short English tags, lowercase, with
words joined by hyphens:
- object: physical things (person, laptop, microphone, car, dog)
- scene: the setting (office, classroom, street, kitchen, outdoors, stage)
- activity: what people are doing (presenting, typing, walking, cooking); use
  "speaking-to-camera" when a person visibly talks to the camera
- attribute: visual qualities (night, close-up, crowded, text-on-screen)
```

and in the same string replace `kind of object (white shirt, sitting, certificate)` with `kind of object (white-shirt, sitting, certificate)`.

Add the import below the `lib.openai_api` import block:

```python
from lib.tags import clean_label
```

In `earlier_batches_text`, replace:

```python
                tags[(tag["label"].strip().lower(), tag["category"])] += 1
```

with:

```python
                tags[(clean_label(tag["label"]), tag["category"])] += 1
```

- [ ] **Step 5: `prepare.py`: build the library through `lib/tags.py`**

Add the import below the `lib.openai_api` import:

```python
from lib.tags import clean_label, tag_library
```

Replace the whole `existing_tags` function with:

```python
def existing_tags(exclude: Path) -> list[dict]:
    """The library's vocabulary, rebuilt from earlier outputs so it never drifts (see
    lib.tags.tag_library; `exclude` is this file's own earlier output)."""
    return tag_library(OUTPUT / PROCESSOR, "tags.json", exclude, MAX_EXISTING_TAGS)
```

Replace the whole `previous_tags` function with:

```python
def previous_tags(output_dir: Path, existing: list[dict]) -> list[dict]:
    """This file's own tags from the result --force replaces, offered for reuse but not
    part of the library (they are still marked new; see finalize.py). Labels saved
    before hyphens that now read the same are counted as one."""
    try:
        tags = json.loads((output_dir / "tags.json").read_text(encoding="utf-8"))[
            "tags"
        ]
    except (OSError, ValueError, KeyError):
        return []
    known = {(t["label"], t["category"]) for t in existing}
    own: dict[tuple[str, str], int] = {}
    for tag in tags:
        key = (clean_label(tag["label"]), tag["category"])
        if key[0] and key not in known:
            own[key] = own.get(key, 0) + len(tag.get("frames") or [0])
    return [
        {"label": label, "category": category, "uses": uses}
        for (label, category), uses in own.items()
    ]
```

Remove `from collections import Counter` (now unused in `prepare.py`).

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: 12 tests, OK

- [ ] **Step 7: Document the format**

`.claude/skills/tag-visuals/SKILL.md`: at the end of the last paragraph (after "...but still count as new."), add:

```
Tags are English, lowercase, with words joined by hyphens (`speaking-to-camera`).
Results saved before this rule still show spaces until tagged again with `force`, but
count as the same tags in the library.
```

`CLAUDE.md`: add this row to the "Layout and naming" table after the `lib/workspace.py` row, keeping the column alignment:

```
| `lib/tags.py`                         | tag wording (English, lowercase, hyphens) and tag libraries rebuilt from results                             |
```

and add this sentence to the end of the paragraph that starts "Visual tags are free-form.":

```
Every tag is English, lowercase, with words joined by hyphens (`speaking-to-camera`);
`lib/tags.py` cleans labels, also those in results saved before this rule.
```

`README.md`, Layout block: after the `lib/openai_api.py` line add:

```
├── lib/tags.py                    tag wording (lowercase, hyphens) and tag libraries
```

- [ ] **Step 8: Hand over for commit (do not commit)**

Message: `feat: join tag words with hyphens in tag-visuals`

---

### Task 3: tag-topics `finalize.py`

**Files:**
- Create: `processors/tag-topics/finalize.py`
- Test: `tests/test_tag_topics_finalize.py`

**Interfaces:**
- Consumes: `lib.tags.clean_label`, `lib.workspace` helpers. It reads two files from the job folder:
  - `plan.json` (written by Task 5):
    ```json
    {
      "version": 1, "processor": "tag-topics", "status": "ready",
      "source": {"name": "x.mov", "path": "/abs/x.mov", "sha256": "…", "kind": "video", "duration_seconds": 130.0},
      "inputs": {"transcript": {"created_at": "2026-11-05T10:00:00+00:00", "complete": true}, "tags": null},
      "options": {"model": "gpt-6-luna", "reasoning_effort": "low"},
      "existing_tags": [{"label": "visa-success-story", "category": "topic", "uses": 2}],
      "visual": ["office", "speaking-to-camera"],
      "refs": {
        "S1": {"source": "speech", "start_seconds": 0.0, "end_seconds": 120.0},
        "T1": {"source": "on_screen_text", "ranges": [[12.0, 20.0]]},
        "V:office": {"source": "visual", "label": "office"}
      },
      "context": "Media: video, 00:02:10 long\n\nSPEECH …",
      "estimated_input_tokens": 2400, "warnings": [],
      "output_dir": "/abs/output/tag-topics/x-1a2b3c4d", "replaces": null,
      "created_at": "2026-11-05T10:05:00+00:00"
    }
    ```
  - `results/answer.json` (written by Task 4): `{"answer": {"summary": str, "tags": [{"label", "category", "confidence", "refs": [str]}]}, "usage": {"input_tokens": int, "output_tokens": int}}`
- Produces:
  - `finalize(job_dir: Path, keep_work: bool = False) -> dict`, which prints nothing and returns `{"status": "complete", "output_dir", "files", "previous_result", "tags": {"type": n, "topic": n, "entity": n}, "tags_dropped": int, "new_tags": int, "usage", "warnings"}`
  - `clean_answer(answer: dict, refs: dict, known: set[str]) -> list[dict]`
  - `CATEGORIES = ("type", "topic", "entity")`

- [ ] **Step 1: Write the failing tests**

`tests/test_tag_topics_finalize.py`:

```python
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from helpers import load_script

finalize = load_script("tag-topics", "finalize")

REFS = {
    "S1": {"source": "speech", "start_seconds": 0.0, "end_seconds": 120.0},
    "T1": {"source": "on_screen_text", "ranges": [[12.0, 20.0]]},
    "V:office": {"source": "visual", "label": "office"},
}


class CleanAnswerTest(unittest.TestCase):
    def test_labels_cleaned_and_repeats_merged(self):
        answer = {"tags": [
            {"label": "Visa Success Story", "category": "topic", "confidence": "high", "refs": ["S1"]},
            {"label": "visa-success-story", "category": "topic", "confidence": "low", "refs": ["T1", "S1"]},
        ]}  # fmt: skip
        [tag] = finalize.clean_answer(answer, REFS, set())
        self.assertEqual(tag["label"], "visa-success-story")
        self.assertEqual(tag["confidence"], "high")
        self.assertEqual([e["ref"] for e in tag["evidence"]], ["S1", "T1"])
        self.assertEqual(tag["evidence"][0]["end_seconds"], 120.0)

    def test_refs_not_sent_are_dropped(self):
        photo_refs = {"V:office": REFS["V:office"]}
        answer = {"tags": [
            {"label": "student-testimonial", "category": "type", "confidence": "medium", "refs": ["S1"]},
            {"label": "office-life", "category": "topic", "confidence": "low", "refs": ["S1", "V:office"]},
        ]}  # fmt: skip
        [tag] = finalize.clean_answer(answer, photo_refs, set())
        self.assertEqual(tag["label"], "office-life")
        self.assertEqual([e["ref"] for e in tag["evidence"]], ["V:office"])

    def test_unknown_category_and_empty_label_dropped(self):
        answer = {"tags": [
            {"label": "the-student", "category": "person", "confidence": "high", "refs": ["S1"]},
            {"label": " - ", "category": "topic", "confidence": "high", "refs": ["S1"]},
        ]}  # fmt: skip
        self.assertEqual(finalize.clean_answer(answer, REFS, set()), [])

    def test_library_tags_not_new(self):
        answer = {"tags": [
            {"label": "Australia", "category": "entity", "confidence": "high", "refs": ["S1"]},
            {"label": "subclass 500", "category": "entity", "confidence": "high", "refs": ["T1"]},
        ]}  # fmt: skip
        tags = finalize.clean_answer(answer, REFS, {"australia"})
        self.assertEqual([(t["label"], t["new"]) for t in tags],
                         [("australia", False), ("subclass-500", True)])


class FinalizeTest(unittest.TestCase):
    def test_writes_outputs_without_the_context(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        job_dir, output_dir = root / "job", root / "out"
        (job_dir / "results").mkdir(parents=True)
        plan = {
            "version": 1, "processor": "tag-topics", "status": "ready",
            "source": {"name": "story.mov", "path": "/x/story.mov", "sha256": "0" * 64,
                       "kind": "video", "duration_seconds": 130.0},
            "inputs": {"transcript": {"created_at": "t1", "complete": True}, "tags": None},
            "options": {"model": "test-model", "reasoning_effort": "low"},
            "existing_tags": [], "visual": ["office"], "refs": REFS,
            "context": "SECRET TRANSCRIPT", "estimated_input_tokens": 100,
            "warnings": [], "output_dir": str(output_dir), "replaces": None,
            "created_at": "t2",
        }  # fmt: skip
        (job_dir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        (job_dir / "results" / "answer.json").write_text(json.dumps({
            "answer": {"summary": "A  student\ntalks about a visa.", "tags": [
                {"label": "Student Testimonial", "category": "type", "confidence": "high", "refs": ["S1"]},
                {"label": "made-up", "category": "topic", "confidence": "low", "refs": ["S9"]},
            ]},
            "usage": {"input_tokens": 90, "output_tokens": 40},
        }), encoding="utf-8")  # fmt: skip

        summary = finalize.finalize(job_dir, keep_work=True)

        document = json.loads((output_dir / "topics.json").read_text(encoding="utf-8"))
        self.assertEqual(document["type"], ["student-testimonial"])
        self.assertEqual(document["topic"], [])
        self.assertEqual(document["visual"], ["office"])
        self.assertEqual(document["summary"], "A student talks about a visa.")
        self.assertEqual(summary["tags"], {"type": 1, "topic": 0, "entity": 0})
        self.assertEqual(summary["tags_dropped"], 1)
        metadata = (output_dir / "metadata.json").read_text(encoding="utf-8")
        self.assertNotIn("SECRET TRANSCRIPT", metadata)
        markdown = (output_dir / "topics.md").read_text(encoding="utf-8")
        self.assertIn("speech 00:00:00-00:02:00", markdown)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: ERROR in `test_tag_topics_finalize`, `FileNotFoundError` for `processors/tag-topics/finalize.py`

- [ ] **Step 3: Write `processors/tag-topics/finalize.py`**

```python
#!/usr/bin/env python3
"""tag-topics, step 3: turn the model's answer into output/tag-topics/<name>-<hash>/
topics.md, topics.json and metadata.json. Free; tag.py runs it.

Each tag keeps the evidence its references point to (a speech part with its times, an
on-screen text, a visual tag); a reference to something that was not sent is dropped,
and so is a tag left with none. Tags not in the library's existing tags are marked new.
Prints only counts and paths, never tags.

    python3 processors/tag-topics/finalize.py work/tag-topics/<job> [--keep-work]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from lib.tags import clean_label
from lib.workspace import (
    archive_previous,
    fail,
    fmt_time,
    is_job_dir,
    now_iso,
    print_json,
    result_metadata,
    write_json,
    write_text,
)

CATEGORIES = ("type", "topic", "entity")
HEADINGS = {"type": "Type", "topic": "Topics", "entity": "Entities"}
CONFIDENCE = ("high", "medium", "low")
INPUT_NAMES = {"transcript": "transcript", "tags": "visual tags"}


def cell(value: str) -> str:
    """Make a value safe inside a Markdown table cell."""
    return value.replace("|", "\\|").replace("\n", " ")


def clean_answer(
    answer: dict[str, Any], refs: dict[str, dict[str, Any]], known: set[str]
) -> list[dict[str, Any]]:
    """The model's tags as stored: labels cleaned (lib.tags), each with the evidence its
    references point to. A tag repeated after cleaning keeps its first confidence and
    gains the other's evidence."""
    kept: dict[tuple[str, str], dict[str, Any]] = {}
    for tag in answer.get("tags", []):
        label = clean_label(str(tag.get("label") or ""))
        category = tag.get("category")
        evidence = [
            {"ref": ref, **refs[ref]}
            for ref in dict.fromkeys(tag.get("refs") or [])
            if ref in refs
        ]
        if not label or category not in CATEGORIES or not evidence:
            continue
        confidence = tag.get("confidence")
        entry = kept.setdefault(
            (label, category),
            {"label": label, "category": category,
             "confidence": confidence if confidence in CONFIDENCE else "low",
             "new": label not in known, "evidence": []},
        )  # fmt: skip
        entry["evidence"] += [e for e in evidence if e not in entry["evidence"]]
    return list(kept.values())


def evidence_text(item: dict[str, Any]) -> str:
    if item["source"] == "speech":
        return f"speech {fmt_time(item['start_seconds'])}-{fmt_time(item['end_seconds'])}"
    if item["source"] == "on_screen_text":
        ranges = item.get("ranges") or []
        return "on-screen text" + (f" {fmt_time(ranges[0][0])}" if ranges else "")
    return f"visual: {item['label']}"


def inputs_line(inputs: dict[str, Any]) -> str:
    return ", ".join(
        INPUT_NAMES[name] + ("" if record["complete"] else " (incomplete)")
        for name, record in inputs.items()
        if record
    )


def to_markdown(plan: dict[str, Any], document: dict[str, Any]) -> str:
    lines = [
        f"# Topics: {plan['source']['name']}",
        "",
        f"- Made from: {inputs_line(document['inputs'])}",
        (
            f"- Model: {document['provider']['model']}; confidence is the model's own "
            "estimate"
        ),
        f"- New tags (not used in this library before): {document['new_tags']}",
        f"- Review status: {document['review_status']}",
        f"- Created: {document['created_at']}",
        "",
        "> Made by a model from what was said, the visual tags and the text read on "
        "screen. People are never named. Check a tag's evidence before relying on it.",
        "",
        "## Summary",
        "",
        document["summary"] or "_No summary._",
    ]
    for category in CATEGORIES:
        entries = [t for t in document["tags"] if t["category"] == category]
        lines.extend(["", f"## {HEADINGS[category]}", ""])
        if not entries:
            lines.append("_None._")
            continue
        lines.extend(["| Tag | Confidence | Evidence |", "| --- | --- | --- |"])
        for tag in entries:
            label = cell(tag["label"]) + (" *(new)*" if tag["new"] else "")
            evidence = "; ".join(evidence_text(e) for e in tag["evidence"])
            lines.append(f"| {label} | {tag['confidence']} | {cell(evidence)} |")
    lines.extend(["", "## Visual tags", "", ", ".join(document["visual"]) or "_None._"])
    return "\n".join(lines) + "\n"


def finalize(job_dir: Path, keep_work: bool = False) -> dict[str, Any]:
    plan = json.loads((job_dir / "plan.json").read_text(encoding="utf-8"))
    answer_file = job_dir / "results" / "answer.json"
    if not answer_file.is_file():
        fail("no answer found; nothing to save (the work folder was kept)")
    result = json.loads(answer_file.read_text(encoding="utf-8"))
    answer = result["answer"]
    known = {tag["label"] for tag in plan["existing_tags"]}
    tags = clean_answer(answer, plan["refs"], known)
    usage = result.get("usage") or {}

    output_dir = Path(plan["output_dir"])
    files = ["topics.md", "topics.json", "metadata.json"]
    archived = archive_previous(output_dir, "topics.json", files, plan.get("replaces"))
    document = {
        "version": 1,
        "processor": plan["processor"],
        "complete": True,
        # Machine-made tags awaiting human review; shown to clients meanwhile.
        "review_status": "staging_pending",
        "source": plan["source"],
        # When each input was made; prepare compares them to notice a newer one.
        "inputs": plan["inputs"],
        "options": plan["options"],
        "provider": {
            "name": "openai",
            "model": plan["options"]["model"],
            "confidence": "model-reported, not calibrated",
        },
        "usage": {
            "requests": 1,
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
        },
        "estimated_input_tokens": plan["estimated_input_tokens"],
        "existing_tags_offered": len(plan["existing_tags"]),
        "new_tags": sum(tag["new"] for tag in tags),
        "visual": plan["visual"],
        **{c: [t["label"] for t in tags if t["category"] == c] for c in CATEGORIES},
        "summary": re.sub(r"\s+", " ", str(answer.get("summary") or "")).strip(),
        "tags": tags,
        "created_at": now_iso(),
    }
    write_json(output_dir / "topics.json", document)
    write_text(output_dir / "topics.md", to_markdown(plan, document))
    # The context holds the transcript, which already has its own result.
    write_json(
        output_dir / "metadata.json",
        result_metadata({k: v for k, v in plan.items() if k != "context"}, "complete"),
    )
    if not keep_work:
        shutil.rmtree(job_dir)

    return {
        "status": "complete",
        "output_dir": str(output_dir),
        "files": files,
        "previous_result": str(archived) if archived else None,
        "tags": {c: len(document[c]) for c in CATEGORIES},
        # Answered tags not kept: no evidence that was sent, or a repeat.
        "tags_dropped": len(answer.get("tags", [])) - len(tags),
        "new_tags": document["new_tags"],
        "usage": document["usage"],
        "warnings": plan["warnings"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--keep-work", action="store_true", help="keep the job folder")
    args = parser.parse_args()
    job_dir = args.job_dir.expanduser().resolve()
    if not is_job_dir(job_dir) or not (job_dir / "plan.json").is_file():
        fail(f"{args.job_dir} is not a prepared job folder inside work/")
    print_json(finalize(job_dir, args.keep_work))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: 17 tests, OK

- [ ] **Step 5: Hand over for commit (do not commit)**

Message: `feat: add tag-topics finalize`

---

### Task 4: tag-topics `tag.py` (the paid request)

**Files:**
- Create: `processors/tag-topics/tag.py`
- Test: `tests/test_tag_topics_tag.py`

**Interfaces:**
- Consumes: `finalize.finalize` and `finalize.CATEGORIES` (Task 3), `lib.openai_api.request`, `output_text`, `OpenAIError`. It reads `plan["options"]["model"]`, `plan["options"]["reasoning_effort"]`, `plan["existing_tags"]` and `plan["context"]`.
- Produces:
  - `INSTRUCTIONS: str` and `SCHEMA: dict`, which Task 5 uses for its token estimate
  - `vocabulary_text(existing: list[dict]) -> str`, which Task 5 uses
  - `build_payload(plan: dict) -> dict`
  - `ask(job_dir: Path, plan: dict) -> OpenAIError | None`, which writes `job_dir/results/answer.json` as `{"answer": {...}, "usage": {...}}`

- [ ] **Step 1: Write the failing tests**

`tests/test_tag_topics_tag.py`:

```python
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import load_script

tag = load_script("tag-topics", "tag")

PLAN = {
    "options": {"model": "test-model", "reasoning_effort": "low"},
    "existing_tags": [{"label": "visa-success-story", "category": "topic", "uses": 2}],
    "context": "Media: video\n\nSPEECH\n\n[S1 00:00:00-00:02:00]\nhello",
}


class PayloadTest(unittest.TestCase):
    def test_text_only_with_context_vocabulary_and_reasoning(self):
        payload = tag.build_payload(PLAN)
        content = payload["input"][0]["content"]
        self.assertEqual({part["type"] for part in content}, {"input_text"})
        texts = " ".join(part["text"] for part in content)
        self.assertIn("[S1 00:00:00-00:02:00]", texts)
        self.assertIn("topic: visa-success-story", texts)
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["reasoning"], {"effort": "low"})
        self.assertTrue(payload["text"]["format"]["strict"])

    def test_unset_effort_sends_no_reasoning(self):
        plan = {**PLAN, "options": {"model": "m", "reasoning_effort": "unset"}}
        self.assertNotIn("reasoning", tag.build_payload(plan))

    def test_instructions_ask_for_hyphens_and_no_names(self):
        self.assertIn("joined by hyphens", tag.INSTRUCTIONS)
        self.assertIn("Never include a person's name", tag.INSTRUCTIONS)


class AskTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.job_dir = Path(temporary.name)
        self.answer_file = self.job_dir / "results" / "answer.json"

    def test_answer_saved(self):
        reply = {"output_text": json.dumps({"summary": "s", "tags": []}),
                 "usage": {"input_tokens": 5, "output_tokens": 2}}  # fmt: skip
        with mock.patch.object(tag, "request", return_value=reply) as sent:
            self.assertIsNone(tag.ask(self.job_dir, PLAN))
        sent.assert_called_once()
        saved = json.loads(self.answer_file.read_text(encoding="utf-8"))
        self.assertEqual(saved, {"answer": {"summary": "s", "tags": []},
                                 "usage": {"input_tokens": 5, "output_tokens": 2}})

    def test_saved_answer_is_not_sent_again(self):
        self.answer_file.parent.mkdir()
        self.answer_file.write_text('{"answer": {"summary": "", "tags": []}}', encoding="utf-8")
        with mock.patch.object(tag, "request", side_effect=AssertionError("paid twice")):
            self.assertIsNone(tag.ask(self.job_dir, PLAN))

    def test_api_error_returned_and_nothing_saved(self):
        error = tag.OpenAIError(429, "rate_limit_exceeded", "slow down")
        with mock.patch.object(tag, "request", side_effect=error):
            self.assertIs(tag.ask(self.job_dir, PLAN), error)
        self.assertFalse(self.answer_file.exists())

    def test_unreadable_answer_is_bad_output(self):
        with mock.patch.object(tag, "request", return_value={"output_text": "not json"}):
            failure = tag.ask(self.job_dir, PLAN)
        self.assertEqual(failure.code, "bad_output")
        self.assertFalse(self.answer_file.exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: ERROR in `test_tag_topics_tag`, `FileNotFoundError` for `processors/tag-topics/tag.py`

- [ ] **Step 3: Write `processors/tag-topics/tag.py`**

```python
#!/usr/bin/env python3
"""tag-topics, step 2: one OpenAI request (paid, text only, never retried) that tags
what the file is about from the material prepare gathered, then writes the outputs
(finalize.py).

The answer is saved in the job folder before finalize runs, so running this again on
the same job sends nothing. Prints only counts and paths, never tags.

    python3 processors/tag-topics/tag.py work/tag-topics/<job>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from finalize import CATEGORIES, finalize

from lib.openai_api import OpenAIError, output_text, request
from lib.workspace import fail, is_job_dir, print_json, write_json

# Reasoning tokens count as output, so leave room beyond the answer itself.
MAX_OUTPUT_TOKENS = 4000

INSTRUCTIONS = """You tag the files of an organisation's media library by what they are
about, so they can be searched. You get one file as text: what was said (a transcript
in the language spoken, in parts S1, S2, ... with their times), tags of what its
pictures show (V:<tag>), and text read on screen (T1, T2, ...). A file may have only
some of these.
Give tags in three categories:
- type: what kind of media this is (student-testimonial, event-recap, advertisement,
  tutorial, interview, certificate)
- topic: what it is about (australia-student-visa, visa-success-story, scholarship)
- entity: specific named things that are not people: countries, cities, schools and
  universities, organisations, programmes, visa subclasses, products (australia,
  subclass-500)
Write every tag in English, lowercase, with words joined by hyphens, whatever language
was spoken. Use the common English name of a place or institution.
Never include a person's name, in a tag or in the summary, even when it is said or
shown on screen; refer to people by their role (the student, the counsellor). SPEAKER 0
and SPEAKER 1 are labels, not names. Do not guess age, ethnicity or emotions.
Tag only what the material supports, and give each tag the references it rests on (S1,
T2, V:office), using only references that appear in the material. Visual tags alone
rarely show what a file is about: rely on speech and on-screen text where there is any.
On-screen text was read by a model and can be wrong.
When the message lists tags already used in this library, treat them as a vocabulary,
not a checklist: reuse one, with its exact wording, only when it describes this file
exactly; otherwise add a new tag.
Give 1 to 3 type tags, up to 10 topic tags and up to 15 entity tags, and a summary of
at most 40 words.
Confidence: high = said or shown plainly; medium = implied or only partly supported;
low = a guess."""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "tags"],
    "properties": {
        "summary": {"type": "string"},
        "tags": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "category", "confidence", "refs"],
                "properties": {
                    "label": {"type": "string"},
                    "category": {"type": "string", "enum": list(CATEGORIES)},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "refs": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


def vocabulary_text(existing: list[dict[str, Any]]) -> str:
    if not existing:
        return (
            "No topic tags have been used in this library yet. Choose clear, general "
            "wording that later files can reuse."
        )
    by_category: dict[str, list[str]] = {}
    for tag in existing:
        by_category.setdefault(tag["category"], []).append(tag["label"])
    lines = [
        f"{category}: {', '.join(labels)}" for category, labels in by_category.items()
    ]
    return (
        "Tags already used in this library (most used first). A vocabulary, not a "
        "checklist: use one only when it describes this file exactly, with the same "
        "wording:\n" + "\n".join(lines)
    )


def build_payload(plan: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": plan["options"]["model"],
        "instructions": INSTRUCTIONS,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": vocabulary_text(plan["existing_tags"])},
                    {"type": "input_text", "text": plan["context"]},
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "topics",
                "strict": True,
                "schema": SCHEMA,
            }
        },
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }
    # Working out what a file is about takes some reasoning, unlike frame tagging.
    effort = plan["options"]["reasoning_effort"]
    if effort != "unset":
        payload["reasoning"] = {"effort": effort}
    return payload


def ask(job_dir: Path, plan: dict[str, Any]) -> OpenAIError | None:
    """Send the request once and save the answer; send nothing when it is saved."""
    answer_file = job_dir / "results" / "answer.json"
    if answer_file.exists():  # paid for in an earlier run
        return None
    try:
        response = request("POST", "/responses", build_payload(plan))
        answer = json.loads(output_text(response))
    except OpenAIError as exc:
        return exc
    except (ValueError, KeyError, TypeError) as exc:
        return OpenAIError(None, "bad_output", f"unexpected answer: {exc}"[:200])
    answer_file.parent.mkdir(exist_ok=True)
    write_json(answer_file, {"answer": answer, "usage": response.get("usage") or {}})
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("job_dir", type=Path)
    args = parser.parse_args()
    job_dir = args.job_dir.expanduser().resolve()
    if not is_job_dir(job_dir) or not (job_dir / "plan.json").is_file():
        fail(f"{args.job_dir} is not a prepared job folder inside work/")
    plan = json.loads((job_dir / "plan.json").read_text(encoding="utf-8"))

    failure = ask(job_dir, plan)
    if failure:
        print_json(
            {
                "status": "failed",
                "job_dir": str(job_dir),
                "error": {
                    "code": failure.code,
                    "status": failure.status,
                    "message": failure.message,
                },
            }
        )
        sys.exit(1)
    print_json(finalize(job_dir))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: 24 tests, OK

- [ ] **Step 5: Hand over for commit (do not commit)**

Message: `feat: add tag-topics request step`

---

### Task 5: tag-topics `prepare.py`

**Files:**
- Create: `processors/tag-topics/prepare.py`
- Modify: `lib/openai_api.py` (add `topic_model`, `estimate_text_tokens`)
- Test: `tests/test_tag_topics_prepare.py`

**Interfaces:**
- Consumes: `tag.INSTRUCTIONS`, `tag.SCHEMA`, `tag.vocabulary_text` (Task 4), `lib.tags.clean_label`, `lib.tags.tag_library`, and the result files of the other processors:
  - `transcript.json`: `{"complete": bool, "created_at": str, "source": {"name", "duration_seconds", ...}, "parts": [{"index", "start_seconds", "end_seconds", "text", "missing"}], ...}`
  - `tags.json`: `{"complete": bool, "created_at": str, "source": {"kind": "video"|"image", "duration_seconds", ...}, "tags": [{"label", "category", "seconds", "frames", ...}] (most frames first), "on_screen_text": [{"text", "legibility", "confirmed"?, "ranges", ...}], ...}`
- Produces:
  - `plan.json` exactly as in Task 3's Interfaces
  - `lib.openai_api.topic_model() -> str`
  - `lib.openai_api.estimate_text_tokens(text: str) -> int`
  - `build_context(transcript: dict | None, tags: dict | None) -> tuple[str, dict, list[str]]`
  - `input_record(result: dict | None) -> dict | None`
  - `previous_status(previous: dict, inputs: dict) -> str`
  - `input_warnings(transcript: dict | None, tags: dict | None) -> list[str]`
  - `visual_labels(tags: dict) -> list[tuple[str, str, float | None]]`

- [ ] **Step 1: Write the failing tests**

`tests/test_tag_topics_prepare.py`:

```python
from __future__ import annotations

import unittest
from unittest import mock

from helpers import load_script

from lib import openai_api

prepare = load_script("tag-topics", "prepare")

TRANSCRIPT = {
    "complete": True, "created_at": "t-transcript",
    "source": {"name": "story.mov", "duration_seconds": 240.0},
    "parts": [
        {"index": 0, "start_seconds": 0.0, "end_seconds": 120.0, "text": "I got my visa.", "missing": False},
        {"index": 1, "start_seconds": 120.0, "end_seconds": 240.0, "text": "Thank you.", "missing": False},
    ],
}  # fmt: skip
TAGS = {
    "complete": True, "created_at": "t-tags",
    "source": {"name": "story.mov", "kind": "video", "duration_seconds": 240.0},
    "tags": [
        {"label": "office", "category": "scene", "seconds": 40.0},
        {"label": "speaking to camera", "category": "activity", "seconds": 30.0},
    ],
    "on_screen_text": [
        {"text": "Subclass 500", "legibility": "clear", "ranges": [[12.0, 20.0]]},
        {"text": "Prof… Sm…", "legibility": "partial", "ranges": [[30.0, 35.0]]},
        {"text": "Guessed line", "legibility": "clear", "confirmed": False, "ranges": [[40.0, 45.0]]},
    ],
}  # fmt: skip


class BuildContextTest(unittest.TestCase):
    def test_speech_visual_and_clear_text_with_refs(self):
        context, refs, warnings = prepare.build_context(TRANSCRIPT, TAGS)
        self.assertEqual(set(refs), {"S1", "S2", "T1", "V:office", "V:speaking-to-camera"})
        self.assertEqual(refs["S2"], {"source": "speech", "start_seconds": 120.0, "end_seconds": 240.0})
        self.assertIn("[S1 00:00:00-00:02:00]\nI got my visa.", context)
        self.assertIn('[T1 00:00:12] "Subclass 500"', context)
        self.assertNotIn("Prof", context)
        self.assertNotIn("Guessed line", context)
        self.assertNotIn("story.mov", context)  # file names can hold people's names
        self.assertEqual(warnings, [])

    def test_photo_without_transcript_has_no_speech(self):
        photo = {**TAGS, "source": {"kind": "image", "duration_seconds": None}}
        context, refs, _ = prepare.build_context(None, photo)
        self.assertNotIn("SPEECH", context)
        self.assertFalse(any(ref.startswith("S") for ref in refs))

    def test_long_transcript_is_cut_with_a_warning(self):
        with mock.patch.object(prepare, "MAX_SPEECH_CHARS", 10):
            context, refs, warnings = prepare.build_context(TRANSCRIPT, None)
        self.assertIn("I got my v", context)
        self.assertNotIn("Thank you", context)
        self.assertEqual(set(refs), {"S1"})
        self.assertEqual(len(warnings), 1)


class InputsTest(unittest.TestCase):
    def test_previous_status_outdated_when_inputs_change(self):
        inputs = {"transcript": prepare.input_record(TRANSCRIPT), "tags": prepare.input_record(TAGS)}
        self.assertEqual(prepare.previous_status({"inputs": inputs}, inputs), "already_done")
        redone = {**inputs, "tags": {"created_at": "t-tags-again", "complete": True}}
        self.assertEqual(prepare.previous_status({"inputs": inputs}, redone), "outdated")
        added = {**inputs, "transcript": None}
        self.assertEqual(prepare.previous_status({"inputs": added}, inputs), "outdated")

    def test_warnings_for_missing_and_incomplete_inputs(self):
        self.assertEqual(len(prepare.input_warnings(None, TAGS)), 1)  # video, no speech
        photo = {**TAGS, "source": {"kind": "image"}}
        self.assertEqual(prepare.input_warnings(None, photo), [])
        partial = {**TRANSCRIPT, "complete": False}
        warnings = prepare.input_warnings(partial, TAGS)
        self.assertEqual(len(warnings), 1)
        self.assertIn("transcript is incomplete", warnings[0])

    def test_visual_labels_cleaned_in_order(self):
        self.assertEqual(
            [label for label, _, _ in prepare.visual_labels(TAGS)],
            ["office", "speaking-to-camera"],
        )


class OpenAISettingsTest(unittest.TestCase):
    def test_topic_model_falls_back_to_vision_model(self):
        values = {"OPENAI_VISION_MODEL": "vision-x"}
        with mock.patch.object(openai_api, "setting", lambda name, default=None: values.get(name, default)):
            self.assertEqual(openai_api.topic_model(), "vision-x")
            values["OPENAI_TOPIC_MODEL"] = "topic-y"
            self.assertEqual(openai_api.topic_model(), "topic-y")

    def test_text_estimate_counts_other_scripts_heavier(self):
        self.assertEqual(openai_api.estimate_text_tokens("abcd" * 10), 10)
        self.assertEqual(openai_api.estimate_text_tokens("नमस्ते"), 3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: ERROR in `test_tag_topics_prepare`, `FileNotFoundError` for `processors/tag-topics/prepare.py`

- [ ] **Step 3: Add the two helpers to `lib/openai_api.py`**

After `estimate_image_tokens`:

```python
def estimate_text_tokens(text: str) -> int:
    """Rough input tokens for text: about 4 characters per token in English, 2 in other
    scripts (Devanagari splits finer). An estimate: a model may count differently."""
    ascii_chars = sum(c.isascii() for c in text)
    return math.ceil(ascii_chars / 4 + (len(text) - ascii_chars) / 2)
```

After `setting`:

```python
def topic_model() -> str:
    """The model tag-topics uses: OPENAI_TOPIC_MODEL, else the tagging model."""
    return (
        setting("OPENAI_TOPIC_MODEL")
        or setting("OPENAI_VISION_MODEL", DEFAULT_VISION_MODEL)
        or DEFAULT_VISION_MODEL
    )
```

(`"नमस्ते"` is 6 code points, none ASCII, so the estimate is 6 / 2 = 3, which matches the test.)

- [ ] **Step 4: Write `processors/tag-topics/prepare.py`**

```python
#!/usr/bin/env python3
"""tag-topics, step 1: gather what transcribe and tag-visuals found for a file into the
material tag.py sends, plus the topic tags already used in output/tag-topics/ (the
folder's topic library). Nothing here costs money. Writes work/tag-topics/<job>/plan.json
and prints a JSON summary, never the transcript or the tags.

    python3 processors/tag-topics/prepare.py input/interview.mov [--force]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `lib`

from tag import INSTRUCTIONS, SCHEMA, vocabulary_text

from lib.openai_api import estimate_text_tokens, setting, topic_model
from lib.tags import clean_label, tag_library
from lib.workspace import (
    OUTPUT,
    fail,
    fmt_time,
    new_job_dir,
    now_iso,
    output_dir_for,
    previous_created_at,
    print_json,
    sha256,
    write_json,
)

PROCESSOR = "tag-topics"
# Most transcript characters sent (about 12,000 tokens of English); the rest is cut.
MAX_SPEECH_CHARS = 48_000
MAX_VISUAL_TAGS = 60  # most seen first
MAX_TEXTS = 60
# Topic tags already in the library, offered to the model for reuse (most used first).
MAX_EXISTING_TAGS = 300


def read_result(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def input_record(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """What topics.json remembers of an input, to notice when it is made again."""
    if result is None:
        return None
    return {
        "created_at": result.get("created_at"),
        "complete": bool(result.get("complete")),
    }


def previous_status(previous: dict[str, Any], inputs: dict[str, Any]) -> str:
    """already_done, or outdated when the transcript or tags were made again (or one was
    added) since these topics were."""
    return "already_done" if previous.get("inputs") == inputs else "outdated"


def input_warnings(
    transcript: dict[str, Any] | None, tags: dict[str, Any] | None
) -> list[str]:
    warnings = []
    if transcript is None and tags and tags.get("source", {}).get("kind") == "video":
        warnings.append(
            "No transcript: topics come from the pictures and on-screen text only. Run "
            "/transcribe first if the video has speech."
        )
    if tags is None:
        warnings.append(
            "No visual tags: topics come from the speech only. Run /tag-visuals first "
            "to include the pictures and on-screen text."
        )
    if transcript is not None and not transcript.get("complete"):
        warnings.append("The transcript is incomplete; topics cover only what it holds.")
    if tags is not None and not tags.get("complete"):
        warnings.append("The visual tags are incomplete; topics cover only what they hold.")
    return warnings


def visual_labels(tags: dict[str, Any]) -> list[tuple[str, str, float | None]]:
    """(label, category, seconds on screen) per visual tag, most seen first. Labels are
    cleaned: results saved before hyphens still have spaces."""
    seen: set[str] = set()
    labels = []
    for tag in tags.get("tags", []):
        label = clean_label(str(tag.get("label") or ""))
        if label and label not in seen:
            seen.add(label)
            labels.append((label, tag.get("category", ""), tag.get("seconds")))
    return labels


def speech_section(
    transcript: dict[str, Any],
) -> tuple[list[str], dict[str, dict[str, Any]], str | None]:
    """The transcript's parts as S1, S2, ... with their times, cut after
    MAX_SPEECH_CHARS. Returns the lines, their references and a warning if cut."""
    parts = [part for part in transcript.get("parts", []) if part.get("text")]
    total = sum(len(part["text"]) for part in parts)
    lines, refs, left = [], {}, MAX_SPEECH_CHARS
    for number, part in enumerate(parts, 1):
        if left <= 0:
            break
        ref = f"S{number}"
        start, end = part["start_seconds"], part["end_seconds"]
        lines.append(f"[{ref} {fmt_time(start)}-{fmt_time(end)}]\n{part['text'][:left]}")
        refs[ref] = {"source": "speech", "start_seconds": start, "end_seconds": end}
        left -= len(part["text"])
    warning = (
        f"The transcript has {total:,} characters; only the first "
        f"{MAX_SPEECH_CHARS:,} are sent, so topics from later speech can be missed."
        if total > MAX_SPEECH_CHARS
        else None
    )
    return lines, refs, warning


def visual_sections(
    tags: dict[str, Any],
) -> tuple[list[str], list[str], dict[str, dict[str, Any]]]:
    """Visual tags as V:<label>, and clearly read, confirmed on-screen text as T1, T2,
    ... Partial or unconfirmed text is left out: it may be misread or invented."""
    visual, refs = [], {}
    for label, category, seconds in visual_labels(tags)[:MAX_VISUAL_TAGS]:
        ref = f"V:{label}"
        visual.append(f"[{ref}] {category}" + (f", on screen {seconds:g} s" if seconds else ""))
        refs[ref] = {"source": "visual", "label": label}
    readable = [
        item
        for item in tags.get("on_screen_text", [])
        if item.get("legibility") == "clear" and item.get("confirmed", True) is not False
    ]
    texts = []
    for number, item in enumerate(readable[:MAX_TEXTS], 1):
        ref = f"T{number}"
        ranges = item.get("ranges") or []
        when = f" {fmt_time(ranges[0][0])}" if ranges else ""
        texts.append(f'[{ref}{when}] "{item["text"]}"')
        refs[ref] = {"source": "on_screen_text", "ranges": ranges}
    return visual, texts, refs


def build_context(
    transcript: dict[str, Any] | None, tags: dict[str, Any] | None
) -> tuple[str, dict[str, dict[str, Any]], list[str]]:
    """The material tag.py sends: a header (kind and length, never the file name, which
    can hold a person's name), speech, visual tags and on-screen text. Returns the text,
    the references finalize maps back to times, and warnings."""
    source = (tags or transcript or {}).get("source", {})
    duration = source.get("duration_seconds")
    header = f"Media: {source.get('kind') or 'audio or video'}" + (
        f", {fmt_time(duration)} long" if duration else ""
    )
    sections, refs, warnings = [header], {}, []
    if transcript:
        lines, speech_refs, warning = speech_section(transcript)
        if lines:
            sections.append(
                "SPEECH (transcript in the language spoken; SPEAKER 0, SPEAKER 1 are "
                "labels, not names)\n\n" + "\n\n".join(lines)
            )
        refs.update(speech_refs)
        if warning:
            warnings.append(warning)
    if tags:
        visual, texts, visual_refs = visual_sections(tags)
        if visual:
            sections.append(
                "VISUAL TAGS (what the pictures show, most seen first)\n"
                + "\n".join(visual)
            )
        if texts:
            sections.append(
                "ON-SCREEN TEXT (read from the frames by a model; can be wrong)\n"
                + "\n".join(texts)
            )
        refs.update(visual_refs)
    return "\n\n".join(sections), refs, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "source", type=Path, help="the file transcribe or tag-visuals ran on"
    )
    parser.add_argument("--force", action="store_true", help="tag again even if done")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        fail(f"file not found: {args.source}")

    digest = sha256(source)
    output_dir = output_dir_for(PROCESSOR, source, digest)
    transcript = read_result(
        output_dir_for("transcribe", source, digest) / "transcript.json"
    )
    tags = read_result(output_dir_for("tag-visuals", source, digest) / "tags.json")
    if transcript is None and tags is None:
        print_json(
            {
                "status": "missing_inputs",
                "message": "Nothing to read yet: run /transcribe or /tag-visuals on this "
                "file first (/process-video runs both).",
            }
        )
        return
    inputs = {"transcript": input_record(transcript), "tags": input_record(tags)}
    previous = output_dir / "topics.json"
    done = read_result(previous)
    if done is not None and not args.force:
        status = previous_status(done, inputs)
        print_json(
            {
                "status": status,
                "output_dir": str(output_dir),
                "message": (
                    "This file's topics are up to date. Use --force to pay again."
                    if status == "already_done"
                    else "The transcript or visual tags were made again (or one was "
                    "added) since these topics were. Use --force to make them again "
                    "(charged again)."
                ),
            }
        )
        return
    # --force: finalize moves the result it replaces into history/ (see archive_previous).
    replaces = previous_created_at(previous)

    context, refs, warnings = build_context(transcript, tags)
    warnings = input_warnings(transcript, tags) + warnings
    existing = tag_library(
        OUTPUT / PROCESSOR, "topics.json", output_dir, MAX_EXISTING_TAGS
    )
    model = topic_model()
    effort = setting("OPENAI_TOPIC_REASONING_EFFORT", "low") or "low"
    source_info = (tags or transcript or {}).get("source", {})
    job_dir = new_job_dir(PROCESSOR, source)
    plan = {
        "version": 1,
        "processor": PROCESSOR,
        "status": "ready",
        "source": {
            "name": source.name,
            "path": str(source),
            "sha256": digest,
            "kind": source_info.get("kind"),
            "duration_seconds": source_info.get("duration_seconds"),
        },
        "inputs": inputs,
        "options": {"model": model, "reasoning_effort": effort},
        "existing_tags": existing,
        "visual": [label for label, _, _ in visual_labels(tags or {})],
        "refs": refs,
        "context": context,
        "estimated_input_tokens": estimate_text_tokens(
            INSTRUCTIONS + json.dumps(SCHEMA) + vocabulary_text(existing) + context
        ),
        "warnings": warnings,
        "output_dir": str(output_dir),
        "replaces": replaces,
        "created_at": now_iso(),
    }
    write_json(job_dir / "plan.json", plan)
    print_json(
        {
            "status": "ready",
            "job_dir": str(job_dir),
            "inputs": {
                "transcript": transcript is not None,
                "visual_tags": tags is not None,
            },
            "paid_requests": 1,
            "model": model,
            "reasoning_effort": effort,
            "estimated_input_tokens": plan["estimated_input_tokens"],
            "existing_tags": len(existing),
            "replaces": replaces,
            "warnings": warnings,
        }
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: 32 tests, OK

- [ ] **Step 6: Smoke-test the free command on a never-processed file (no paid call)**

Use the session scratchpad (or any temp folder outside the repo) for a throwaway file:

Run: `printf 'never processed' > "$SCRATCH/topics-smoke.bin" && python3 processors/tag-topics/prepare.py "$SCRATCH/topics-smoke.bin"; rm -f "$SCRATCH/topics-smoke.bin"` (set `SCRATCH` to that folder first)
Expected: `{"status": "missing_inputs", ...}`, and `ls work/tag-topics 2>/dev/null` shows no new job folder.

- [ ] **Step 7: Hand over for commit (do not commit)**

Message: `feat: add tag-topics prepare`

---

### Task 6: Skill, permissions, pipeline, setup and docs

**Files:**
- Create: `.claude/skills/tag-topics/SKILL.md`
- Modify: `.claude/settings.json`
- Modify: `.claude/skills/process-video/SKILL.md`
- Modify: `scripts/check_setup.py` (`openai_model_check`, `main`, docstring)
- Modify: `.claude/skills/setup/SKILL.md`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: the JSON that `prepare.py`, `tag.py` and `finalize.py` print (Tasks 3-5): statuses `missing_inputs`, `already_done`, `outdated`, `ready`, `complete`, `failed`, and the `error.code` values `bad_output`, `missing_key` plus the OpenAI codes.
- Produces: `/tag-topics`, and `/process-video` running it as its last processor.

- [ ] **Step 1: Write `.claude/skills/tag-topics/SKILL.md`**

```markdown
---
name: tag-topics
description: Tag what a video, audio file or photo is about (type, topics, named things) from its transcript, visual tags and on-screen text, with one OpenAI text request (paid). Runs only when the user types /tag-topics.
argument-hint: <file> [force]
disable-model-invocation: true
---

# Tag topics

Request: `$ARGUMENTS`

Processor: `processors/tag-topics/`. Steps: prepare (free, local) → tag (paid, one OpenAI
request, text only, also runs finalize). It reads the results `/transcribe` and
`/tag-visuals` saved for the same file and never sends the file itself. Do not open
`topics.md` or `topics.json` unless the user asks.

## 1. Prepare

Run `python3 processors/tag-topics/prepare.py <file>`, adding `--force` if the user says
again, redo or force. If the file is not found, look in `input/` for a close match and
ask before using it.

Read the JSON it prints:

- `"status": "missing_inputs"`: nothing to read yet. Suggest `/transcribe`, `/tag-visuals`,
  or `/process-video` for both. Stop.
- `"status": "already_done"`: tell the user where the output is and that `force` would be
  charged again (the current result then moves to `history/`). Stop.
- `"status": "outdated"`: the transcript or the visual tags were made again, or one was
  added, after these topics were made. Offer `force` (charged again). Stop.
- `"status": "ready"`: tell the user which inputs it read (`inputs`), that it is one paid
  request, the model and reasoning effort, and the estimated input tokens
  (`estimated_input_tokens`, rough; reasoning adds output tokens). Quote any `warnings`
  word for word. If `replaces` is set, say that the current result moves to `history/`
  in the output folder when the new one is saved.

## 2. Tag

Run `python3 processors/tag-topics/tag.py <job_dir>` once, with `job_dir` from step 1.
Never retry it, and never reach OpenAI any other way. If it stopped after the answer
arrived, running it again on the same job sends nothing and only writes the outputs.

Read the JSON it prints:

- `"status": "complete"`: go to step 3.
- `"status": "failed"`: explain `error.code`:
  - `invalid_api_key` or status 401: the OpenAI key is wrong.
  - `model_not_found`, status 403 or 404: the key cannot use this model; set
    `OPENAI_TOPIC_MODEL` in `.env` to one it can use.
  - `insufficient_quota`: no credits left on the OpenAI account.
  - `rate_limit_exceeded`: too many requests; try again later.
  - `network`: the connection failed; the request may or may not have been charged.
  - `missing_key`: `OPENAI_API_KEY` is not in `.env`; suggest `/setup`.
  - `bad_output`: the answer arrived (and was charged) but could not be read. Do not
    run it again without asking the user.

## 3. Report

In a few lines: the output folder, the files (`topics.md`, `topics.json`,
`metadata.json`), where the replaced result went (`previous_result`, if set), the number
of tags per category (`tags`: type, topic, entity), how many are new to the library
(`new_tags`), how many tags the model gave that were dropped because their evidence was
not in what was sent, or because they repeated another (`tags_dropped`), the requests
and tokens used (`usage`), and any warnings. Do not list the tags or the summary unless
the user asks. Topic tags are made by a model: each lists its evidence (speech times,
on-screen text, visual tags) so it can be checked, and they await review
(`review_status: staging_pending`). People are never named. Never present them as
verified.

Tags are English, lowercase, with words joined by hyphens. To keep wording consistent,
`prepare.py` offers the topic tags already used in `output/tag-topics/` as a vocabulary;
tags new to it are marked `new` in `topics.json` and `(new)` in `topics.md`.
```

- [ ] **Step 2: `.claude/settings.json` permissions**

In `allow`, after `"Bash(python3 processors/tag-visuals/finalize.py *)",` add:

```json
      "Bash(python3 processors/tag-topics/prepare.py *)",
      "Bash(python3 processors/tag-topics/finalize.py *)",
```

In `ask`, after `"Bash(python3 processors/tag-visuals/tag.py *)",` add:

```json
      "Bash(python3 processors/tag-topics/tag.py *)",
```

Check that the JSON still parses: `python3 -c "import json; json.load(open('.claude/settings.json'))"`

- [ ] **Step 3: `/process-video` runs tag-topics last**

In `.claude/skills/process-video/SKILL.md`:

Replace the `description:` line with:

```
description: Run every video processor on one video - speech transcription (ElevenLabs) and visual tagging (OpenAI) in parallel, then topic tagging (OpenAI) from both results (paid). Runs only when the user types /process-video.
```

Replace the paragraph starting "Runs the `transcribe` and `tag-visuals` processors" (it ends "Follow them, except for the order below.") with:

```
Runs the `transcribe` and `tag-visuals` processors on the same video, with visual tagging
in the background while the transcription runs, then `tag-topics` on both results. Read
`.claude/skills/transcribe/SKILL.md`, `.claude/skills/tag-visuals/SKILL.md` and
`.claude/skills/tag-topics/SKILL.md` now: they define each processor's flags, statuses,
paid calls and error messages. Follow them, except for the order below.
```

Replace `` - `force` → both. `` with `` - `force` → all three. ``

At the end of section 1 (after "...and describe only options that prepare printed."), add:

```
Add a third line: one more OpenAI request (topics, text only) follows once both are done;
its estimate is shown before it is sent.
```

Rename `## 5. Report` to `## 6. Report`, and insert this section before it:

```
## 5. Tag topics

When both have finished, or one had nothing to do, follow steps 1 and 2 of the tag-topics
skill on the same video, with `--force` if the request had `force`. Show its plan (step 1,
`ready`) in one line before running `tag.py`. If prepare says `missing_inputs`,
`already_done` or `outdated`, report that and go on to the report. A failure here does
not undo the other two.
```

In the Report section, replace "One short section per processor" with "One short section per processor (transcribe, tag-visuals, tag-topics)".

- [ ] **Step 4: `/setup` checks the topic model**

In `scripts/check_setup.py`, add `topic_model` to the `lib.openai_api` import list, then replace `openai_model_check` with:

```python
def openai_model_check(model: str, name: str) -> tuple[str, bool, str]:
    try:
        request("GET", f"/models/{model}", timeout=15)
    except OpenAIError as exc:
        return name, False, f"{model}: {exc.code} {exc.message[:80]}"
    return name, True, f"{model} usable with this key"
```

In `main()`, replace:

```python
        key_check("OPENAI_API_KEY", "needed by /tag-visuals"),
    ]
    if key_source("OPENAI_API_KEY"):
        checks.append(openai_model_check())
```

with:

```python
        key_check("OPENAI_API_KEY", "needed by /tag-visuals and /tag-topics"),
    ]
    if key_source("OPENAI_API_KEY"):
        vision = setting("OPENAI_VISION_MODEL", DEFAULT_VISION_MODEL) or DEFAULT_VISION_MODEL
        checks.append(openai_model_check(vision, "OpenAI model access"))
        if topic_model() != vision:
            checks.append(openai_model_check(topic_model(), "OpenAI topic model"))
```

In the module docstring, replace "whether the key can use the vision model" with "whether the key can use the vision model (and the topic model, if set apart)".

Run: `python3 -c "import ast; ast.parse(open('scripts/check_setup.py').read())"`
Expected: no output. Do not run `check_setup.py` itself here: it reads `.env` through `lib`, so the user runs `/setup`.

In `.claude/skills/setup/SKILL.md`:

- In the `description:` line, replace "OpenAI vision model" with "OpenAI models".
- Replace:

  ```
     - OpenAI model access: the script asked OpenAI (free) whether the key can use the
       vision model. `invalid_api_key` = wrong key; `model_not_found` = set
       `OPENAI_VISION_MODEL` in `.env` to a model the key can use.
  ```

  with:

  ```
     - OpenAI model access / OpenAI topic model: the script asked OpenAI (free) whether
       the key can use the vision model, and the topic model when `OPENAI_TOPIC_MODEL`
       is set to another one. `invalid_api_key` = wrong key; `model_not_found` = set
       `OPENAI_VISION_MODEL` (tagging) or `OPENAI_TOPIC_MODEL` (topics) in `.env` to a
       model the key can use.
  ```

- Replace the last paragraph:

  ```
  End with one line each for `/transcribe` (ElevenLabs key and MCP tools), `/tag-visuals`
  (OpenAI key and model access) and `/process-video` (both): ready, or what is missing.
  ```

  with:

  ```
  End with one line each for `/transcribe` (ElevenLabs key and MCP tools), `/tag-visuals`
  and `/tag-topics` (OpenAI key and model access) and `/process-video` (all): ready, or
  what is missing.
  ```

- [ ] **Step 5: `.env.example`**

Replace `# /tag-visuals - key from https://platform.openai.com/api-keys` with `# /tag-visuals and /tag-topics - key from https://platform.openai.com/api-keys`, and append at the end of the file:

```
# Model for /tag-topics (text only); default: the vision model above.
# OPENAI_TOPIC_MODEL=gpt-6-luna
# Reasoning effort for topics (default low); "unset" sends no reasoning setting.
# OPENAI_TOPIC_REASONING_EFFORT=low
```

- [ ] **Step 6: `README.md`**

Processor table: add after the `tag-visuals` row (keep column alignment):

```
| tag-topics  | `/tag-topics`  | a file already transcribed or tagged | what it is about: type, topics and named things (never people), each with its evidence, and a short summary (`.md`, `.json`) | OpenAI text model (official API)                |
```

Pipeline table: replace the `process-video` row's last cell with `` `transcribe` and `tag-visuals` on one video, in parallel, then `tag-topics` ``.

After the paragraph starting "`/process-video` runs both columns at the same time", add:

```
When both are done, `tag-topics` reads the transcript, the visual tags and the clearly
read on-screen text (never the file) and asks OpenAI, in one text request, what the
video is about: its type (`student-testimonial`), topics (`australia-student-visa`) and
named things (`subclass-500`). Every tag is English, lowercase, with hyphens.
```

Words table: change the `force` row's Processor cell from `both` to `all`.

Results block: after the `output/tag-visuals/...` tree add:

```
output/tag-topics/interview-1a2b3c4d/
├── topics.md         type, topics and entities with their evidence (speech times,
│                     on-screen text, visual tags), new tags marked, and the summary
├── topics.json       the same, plus `visual` (the file's visual tags), confidence,
│                     review status, the inputs it read, tokens used
├── metadata.json     inputs, model, request plan, status
└── history/<time>/   earlier results that `force` replaced (only after a `force`)
```

Safety and cost: in "**Paid steps always ask.**" replace "the OpenAI tagging script" with "the OpenAI tagging scripts (visual tags and topics)". In "**Providers only see prepared files.**", after "...a full-resolution crop around that text." add "For topics, OpenAI receives the transcript text, the visual tags and the clearly read on-screen text, never a file."

- [ ] **Step 7: `CLAUDE.md`**

In Rules, replace `` OpenAI through `processors/tag-visuals/tag.py` `` with `` OpenAI through `processors/tag-visuals/tag.py` and `processors/tag-topics/tag.py` ``.

After the paragraph starting "Visual tags are free-form.", add:

```
Topic tags (`tag-topics`: type, topic, entity) come from a file's transcript, visual tags
and on-screen text in one text request; each cites its evidence, and none names a
person. Their library is `output/tag-topics/*/topics.json`, rebuilt the same way.
```

- [ ] **Step 8: Run the whole suite**

Run: `python3 -m unittest discover -s tests -v`
Expected: 32 tests, OK

- [ ] **Step 9: Hand over for commit (do not commit)**

Message: `feat: add /tag-topics and run it in /process-video`

---

### Task 7: End-to-end check with the user (paid, only with approval)

**Files:** none

- [ ] **Step 1: Ask the user** which already processed file to use (one with both a transcript and visual tags), and say that this costs one OpenAI request.
- [ ] **Step 2: With their go-ahead,** run `/tag-topics <file>`, following its skill. Report only the statuses, counts and paths it prints; do not open `topics.md` unless the user asks.
- [ ] **Step 3: Note the real `usage.input_tokens`** against `estimated_input_tokens`. If they differ by more than 30 %, propose adjusting `estimate_text_tokens` (do not change it unasked).
