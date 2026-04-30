# KAIJU HUD — PHASE 2 MASTER ARCHITECTURE DOCUMENT
# Version 1.0 | Read this before every stage. Never deviate from it.

---

## PURPOSE OF THIS DOCUMENT

This is the north star for all Phase 2 work on the Kaiju Command Bridge HUD.
Every stage instruction references this document. If a stage instruction
conflicts with this document, this document wins. Flag the conflict, do not
silently resolve it by guessing.

---

## WHAT PHASE 2 IS

Phase 2 transforms the Kaiju HUD from a parallel multi-AI chat interface into
a Bobby-orchestrated sequential Mixture-of-Agents (MoA) pipeline with RAG
memory retrieval. 

Phase 1 parallel dispatch is NOT removed. It remains intact as a fallback.
Phase 2 is a new code path added alongside Phase 1, not a replacement.

---

## THE CAST

- **Bobby Bee** — Local LLM via Ollama. Column 5. Orchestrator, librarian,
  memory owner. Runs first (research), runs last (synthesis). Never writes code.
- **Claude** — Column 1. Default designated coder for all projects.
- **ChatGPT** — Column 2. Evaluator/thinker only unless designated coder.
- **Grok** — Column 3. Evaluator/thinker only unless designated coder.
- **Copilot** — Column 4. Evaluator/thinker only unless designated coder.

---

## THE FULL PIPELINE (PHASE 2 MOA MODE)

```
User sends prompt
        ↓
Bobby receives it FIRST (before any other AI)
Bobby runs keyword extraction via local LLM call
Bobby searches full_sessions DB using extracted keywords
        ↓
BRANCH: What did Bobby find?
  → Found session flagged COMPLETE:
        Bobby surfaces to user:
        "We completed this on [date/time]. Enhancement or did you forget?"
        WAIT for user response. Do not proceed until response received.
        User says "enhance" → inject old context, run chain
        User says "forget" / "new" → run chain fresh
        User says "unrelated" → run chain ignoring old results

  → Found session flagged PARTIAL/IN-PROGRESS:
        Bobby surfaces to user:
        "Found related discussion from [date] about [topic].
         Relevant context or different direction?"
        WAIT for user response.

  → Found nothing relevant:
        Proceed immediately, no user interruption.
        ↓
Bobby constructs Claude prompt:
  [retrieved context if any] + [original user prompt]
Bobby fires Claude. WAITS for full response. Stores response.
        ↓
Bobby constructs ChatGPT prompt:
  [original prompt] + [Claude full response] +
  "You are AI 2 in a multi-agent chain. Evaluate the previous AI's response.
   Show where you agree, where you disagree, and what you would add or change."
Bobby fires ChatGPT. WAITS for full response. Stores response.
        ↓
Bobby constructs Grok prompt:
  [original prompt] + [Claude response] + [ChatGPT response] +
  same evaluation instruction referencing both previous outputs
Bobby fires Grok. WAITS. Stores.
        ↓
Bobby constructs Copilot prompt:
  [original prompt] + [Claude] + [ChatGPT] + [Grok] +
  same evaluation instruction referencing all three
Bobby fires Copilot. WAITS. Stores.
        ↓
Bobby synthesizes all four responses.
Bobby writes to DB:
  - bobby_response (synthesis)
  - bobby_lesson (one-paragraph distillation)
  - keywords (extracted terms)
  - topic (short label)
  - status → IN_PROGRESS
  - project_id (if active project)
Round complete. User sees all outputs + Bobby synthesis.
```

---

## NO-LOOP GUARANTEE

This is non-negotiable. Enforce at the dispatcher level.

- Each AI receives EXACTLY ONE call per MoA round.
- No retries within the MoA chain. If an AI fails, Bobby notes it and
  continues to the next AI. The failed slot is marked null in the DB row.
- Bobby does NOT re-trigger the chain after synthesis.
- The background watcher in OllamaClient does NOT trigger synthesis for
  MoA rounds. MoA rounds manage their own lifecycle.
- A round_mode flag ("parallel" | "moa") is set at round open and governs
  which path runs. Never both simultaneously.

---

## SEND TO CODER FLOW

```
User reviews all outputs and Bobby synthesis.
        ↓
OPTIONAL: User says "Bobby, run final pass"
  → Bobby sends complete build context to all 4 AIs simultaneously
  → Each re-evaluates the FULL approved output
  → Bobby synthesizes confirmation
  → This is stored as a REVIEW pass, not a new round
        ↓
User says "Bobby, send to coder"
  → Bobby looks up active project's designated_coder column
  → Bobby checks storage/forbidden_ruleset.db
      EXISTS → read all rules for project's language tag → inject
      MISSING → skip, no error, no warning
  → Bobby packages:
      - Original user prompt
      - All AI responses from the round
      - Bobby synthesis
      - Approved final pass synthesis (if run)
      - Forbidden rules (if found)
      - Project context (name, language, description)
  → Bobby fires designated coder column ONLY
  → Coder writes output to Projects/[ProjectName]/
  → Bobby logs the send event to DB
  → Bobby confirms to user: "Sent to [AI name]. Writing to Projects/[ProjectName]/"
```

---

## PROJECT SYSTEM

### What a project is
A named workspace. Has a designated coder, a language tag, a status, and
maps to a subfolder under the Projects/ directory.

### Project commands Bobby understands (plain English, fuzzy match ok)
- "new project [name]" → creates project record + Projects/[name]/ folder
- "set coder [AI name or column number]" → updates designated_coder
- "set language [language]" → updates language tag for ruleset lookup
- "close project" → sets status to COMPLETE
- "what project are we on" → Bobby states current active project

### One active project at a time per session
Bobby tracks _active_project_id in memory. Persists to DB.

---

## FOLDER STRUCTURE

```
kaiju_hud/                    ← ROOT (dynamic, never hardcoded)
├── main.py
├── core/
├── providers/
├── local_llm/
├── storage/
│   ├── kaiju_hud.db          ← existing
│   └── forbidden_ruleset.db  ← optional, checked at send-to-coder time
├── config/
├── Projects/                 ← NEW — all AI-generated output lives here
│   ├── ProjectName_1/
│   ├── ProjectName_2/
│   └── ...
└── ui/
```

### Root detection rule
The Kaiju HUD root is always resolved relative to the location of main.py.
Use pathlib: `ROOT = Path(__file__).resolve().parent` in any file that
needs the root. Never use os.path with hardcoded drive letters.
Never use D:\\, C:\\, or any absolute path anywhere in the codebase.

---

## FILEBROKER RULES

- FileBroker ROOT must be dynamic (relative to main.py location).
- All file writes go through FileBroker.
- FileBroker write() must support subdirectory creation automatically
  (os.makedirs already present — keep it).
- FileBroker gets a new method: `ensure_project_folder(project_name)` →
  creates Projects/[project_name]/ if it doesn't exist, returns the path.
- The hardcoded `D:\\AI\\kaiju_hud` string in claude_provider.py FILE_SYSTEM_PREFIX
  must be replaced with dynamic root resolution.

---

## DATABASE CONVENTIONS

- All databases live in storage/
- All new tables added to kaiju_hud.db (not separate files) unless the
  table is forbidden_ruleset.db which is its own optional file
- All new columns use snake_case
- Never drop or rename existing columns
- Never modify existing table schemas — only ADD new columns/tables
- All timestamps stored as ISO 8601 UTC strings
- All JSON blobs stored as TEXT columns, parsed in Python

---

## BOBBY BEE BEHAVIORAL RULES

- Bobby speaks in first person, direct, with personality. Not robotic.
- Bobby always tells the user what he found before proceeding.
- Bobby always waits for user confirmation when surfacing a found session.
- Bobby never silently ignores a relevant past session.
- Bobby has sass. If the user asks for something already built and marked
  complete, Bobby calls it out directly with the date and asks if they forgot.
- Bobby tracks one active project at a time.
- Bobby is the ONLY entity that writes to bobby_lesson and bobby_response columns.
- Bobby does NOT write code. Bobby orchestrates who writes code.

---

## NEVER VIOLATE THESE RULES

1. No hardcoded paths anywhere. Ever.
2. No loops in the MoA chain. One pass per AI per round.
3. Phase 1 parallel dispatch is not touched or removed.
4. Existing DB columns and tables are not modified or dropped.
5. Bobby does not write code to Projects/ — only the designated coder does.
6. forbidden_ruleset.db missing is not an error. Skip silently.
7. All new files follow existing naming conventions (snake_case, no spaces).
8. Claude Code must verify each stage completion checklist before stopping.
9. Do not implement future stages while working on the current stage.
10. If anything is ambiguous, stop and flag it. Do not guess.

---

## STAGE OVERVIEW (do not implement ahead — listed for awareness only)

- Stage 1: DB schema additions + Projects/ folder structure + FileBroker fix
- Stage 2: Bobby keyword extraction + DB search + intent surfacing to user
- Stage 3: Sequential MoA chain wired into Bobby (no-loop enforced)
- Stage 4: Project management commands + designated coder tracking
- Stage 5: Send to coder — forbidden ruleset check + coder dispatch + file write
- Stage 6: Final confirmation pass + UI project context display

---

## ECHO DECK CONTEXT (why this matters)

The primary production use case driving this system is the Echo Deck —
a modular PySide6 AI companion application with 35+ modules across 10
categories. Each module is its own project. The Kaiju HUD MoA pipeline
will be used to design, evaluate, and build each module with all AIs
contributing, LSL forbidden rules injected where relevant, and Claude
(or designated coder) writing the final output to Projects/[ModuleName]/.

This is not a toy. Build it right.

---

END OF MASTER DOCUMENT
