---
name: brainbase-conversation-workflow-builder
description: Create or edit the workflow JSON (nodes + edges) that drives an AI voice call assistant. Fills in what the request already says and asks at most 5 questions (inbound/outbound, required inputs, outcomes, safeties), then returns validated JSON plus a summary. Use for a plain-language call flow request, or an existing workflow JSON plus a change.
---

# Brainbase Conversation Workflow Builder

Produces valid `workflow_definition` JSON for an AI call assistant: a graph of nodes (conversation steps, code steps, endings, post-call actions) and edges (transitions). Two modes:

- **Create:** plain-language request → new workflow.
- **Edit:** existing workflow JSON + requested change → minimally changed workflow.

Every new workflow starts by filling in what the request already says and asking **at most 5 questions** about the rest, then returns **valid JSON plus a brief, plain-language explanation** of what was built or changed (no talk of nodes or edges).

## Bundled references (read before writing JSON)

| File | Read when |
| --- | --- |
| `references/intake.md` | Create mode, before anything else: the question bank for interviewing the requester and how answers map to the workflow. |
| `references/schema.md` | Always. Node types, every allowed field and default, edge fields, graph constraints, fields that do not exist. |
| `references/routing-context-code.md` | Always for routing; essential whenever there is a codeNode, an expression edge, extracted data reused later, or `{{variables}}`. |
| `references/authoring-gotchas.md` | Always. Graph design, voice prompt writing, edge conditions, known production failures. |
| `references/editing.md` | Edit mode. Preserving ids, rewiring, change-summary format, common edit recipes. |
| `examples/appointment_confirmation.json` | Shape to copy (outbound): name-free greeting, voicemail branch, identity check with a separate second-attempt step, callback time collected before the ending, several outcome-named endings, webhook with outcome and phone number, QA. |
| `scripts/validate_workflow.py` | Run on every output (and on the input in edit mode). `--add-positions` fills in missing node positions first. |
| `scripts/diff_workflows.py` | Edit mode, internal check: confirms only the intended parts changed. Its output is for you, not the requester. |

If you cannot run Python, use the manual checklist at the end of `references/schema.md`.

## Process: Create mode

1. **Fill in, then ask at most 5 questions** (`references/intake.md`). First answer everything you can from the request itself. Then ask only the most important remaining gaps (often 0–2 questions for a detailed request), in one short message with a suggested default for each. Priority: inbound/outbound and how calls start → required contact information → outcomes and what happens in each → safety specifics (disclosures, never-say rules, identity check) → where results go. Everything else gets a default, listed under **Assumptions** in the response. If the request is complete, or the requester says "just build it", skip the questions.
2. **Sketch the graph** in text first: each node with its outgoing edges (`label → target`). Check that each LLM node has an exit for every realistic answer, and every path reaches an endCall.
3. **Write the JSON** using the schema. Follow `examples/appointment_confirmation.json` for shape and style. **Give every node a `position`** (`x` = 400 × steps from the start, `y` = 250 × branch number): a workflow missing any position saves but fails validation and won't run.
4. **Validate:** save to `workflow.json`, run `python3 scripts/validate_workflow.py --add-positions workflow.json` (fills in any missing positions, then validates), fix every ERROR, rerun until 0 errors. Then resolve every WARN: fix it, or, for an input that is required on purpose (every call will provide it), declare it with `--inputs name1,name2` so it stops warning. The greeting warning can be left when the variable isn't personal, like a per-call `{{company_name}}` (see "Voicemail" in `references/authoring-gotchas.md`). Mention anything the requester must act on under **Heads-up** in plain words.
5. **Review the design** (the validator can’t): for each LLM node, list what a real caller might say and confirm an edge covers it; for each codeNode, ask what happens if every `context.get` returns its default.
6. **Respond** in the output format below.

## Process: Edit mode

1. If the change raises open questions (e.g. new webhook → endpoint and fields; new branch → where should each answer go?), ask only those (at most 2), in one message, before editing. See “Edit mode” in `references/intake.md`.
2. Identify the input shape (bare definition, full saved object with `workflow_definition` inside, or a fragment) and return the same shape. See `references/editing.md`.
3. Run the validator on the **input** first and note pre-existing errors/warnings. Problems already in the workflow go under Heads-up and aren't fixed, unless the requester asked or the change can't work without it. The one exception is missing positions, because the workflow won't run as given: add them (`--add-positions`) and say so under Heads-up.
4. Make the minimal change. Never rename existing ids. Rewire completely when inserting or deleting nodes. Match the existing language, tone and naming style. Don’t touch unrelated content.
5. Validate the output with `--add-positions` (and `--inputs` for the workflow's intentionally required inputs): every node (including new ones) must have a position, and there must be no new errors or warnings. Warnings that were already in the input can stay, and so can the greeting warning for a variable that isn't personal, like a per-call `{{company_name}}`.
6. Run `python3 scripts/diff_workflows.py before.json after.json` and confirm the diff contains only what you intended.
7. Respond in the output format below, including the summary of changes.

## Output format

The requester cares about what the call does, not how the JSON is built. Everything outside the JSON is short, plain language: **no mention of nodes, edges, ids, labels, conditions, node types or field names.** Describe the call the way you'd explain it to a colleague ("The agent confirms it's the patient, checks their birth year, then confirms the appointment").

1. **Assumptions** (only if you proceeded without answers): each default you chose, one short line each.
2. **Workflow JSON** in one ```json code block (or as a `.json` file if files are supported), 2-space indented, strict JSON (no comments, no trailing commas).
3. **What it does** (new workflows): 2–5 sentences, or a few short bullets, walking through the call from greeting to the possible endings, and what happens after the call (results sent, quality review).
   **What changed** (edits): 1–5 short bullets describing the change in behavior ("Callers who ask to be called back are now asked for a day and time before the call ends"). Format in `references/editing.md`.
4. **What to provide:** the information each call needs (required vs. optional, with the column/field names they'll fill in — the only technical names allowed here), including inputs only read in code (like a ZIP code that's checked but never spoken), and anything to plug in before going live (tools, documents, webhook URL, credentials), in plain words.
5. **Safeguards** (one line): the protections built in, e.g. identity check before sharing details, honest AI disclosure, polite opt-out, hand-off to a human.
6. **Heads-up** (only if needed): anything already broken in an edited workflow, or other issues noticed, in plain words. Don't report validator output, warnings or counts unless something needs the requester's action.

Keep it brief; the JSON is the deliverable.

## Rules that matter most (details in references)

- Node types: `startCall` (exactly 1), `agentNode`, `endCall`, `globalNode` (≤1), `codeNode`, `webhook`, `qa`, `trigger` (≤1), `tuner` (≤1). Anything else is rejected.
- Unknown `data` keys are silently stripped on save. Never generate `wait_for_user_response`, `wait_for_user_response_timeout`, `detect_voicemail`, `is_start`, `is_end`, or UI fields.
- `globalNode`, `webhook`, `qa`, `tuner` have **no edges**. Leave `trigger` unconnected; calls always begin at `startCall`.
- `startCall`: 0 incoming. `agentNode`: ≥1 incoming, should have outgoing edges. `endCall`: ≥1 incoming, 0 outgoing. `codeNode`: ≥1 in, ≥1 out.
- Every edge needs non-empty `label` **and** `condition` (even expression/always edges). Labels: short ASCII snake_case, unique per source node after normalization; they become the LLM’s transition function names.
- Only LLM edges (default) work out of `startCall`/`agentNode`. `expression` and `always` edges only work out of a `codeNode`; each codeNode needs exactly one `always` edge. Make it the safe exit when you can; when the safe exit would share a target with another route, make the code fail safe instead (see "Code node defaults" in `routing-context-code.md`).
- **Only one edge between any two nodes**; a second one is silently dropped. Merge conditions that lead to the same next step.
- Deterministic checks (matching digits, math) go in a codeNode, not in the LLM.
- **Retries: one ask step per attempt.** Never route a failed answer back to the same ask step; the agent can ignore the second answer and stall. Ask → check → ask again (own step, own extraction variable, re-ask wording in its prompt) → check again → polite exit. Cap at 2–3 attempts.
- **Endings only say goodbye.** The call hangs up right after an ending's line, so an ending's prompt never asks a question or collects anything; do that in an agentNode before it.
- **Report the outcome deterministically:** name each ending after its outcome and send `{{gathered_context.nodes_visited}}` in the webhook (last item = ending reached), or stamp `call_outcome` with a codeNode before each ending. If the requester asks for an "outcome" field, use the stamp. Never ask the AI to fill in an outcome value.
- **Outbound calls:** always add a voicemail branch from startCall to a neutral voicemail ending, and keep personal details out of the greeting (it plays before voicemail can be recognized).
- **Greeting asks who's speaking:** add to the startCall prompt: "If the answer is unclear, ask for their name. Never mention the account before identity is confirmed." (Swap "account" for what the call is about.) Let it re-ask only twice, then route to a polite ending if the answer is still unclear.
- **Company name changes per call:** use `{{company_name}}` in the greeting. It isn't personal, so its greeting warning can be left.
- **Contact's phone number in results:** `{{initial_context.called_number}}` on outbound calls, `{{initial_context.caller_number}}` on inbound.
- **Every node needs a `position`.** Without one the workflow saves but won't run. If you can't add them, say plainly that the workflow won't work as-is.
- Code nodes: standard-library Python, **no network, no integration imports**, read with `context.get(k, default)`, write only to `outputs`, keep fast.
- Extracted variables are **not** visible in later prompts. Copy them through a codeNode output if a later prompt must say them; otherwise rely on conversation history.
- `{{var}}` without a fallback is a required input. Use `{{var | fallback}}` for optional values; if the fallback text has a colon, use `{{var | fallback:text: with colon}}`. Variables work the same in the shared persona prompt as in step prompts. Don’t name a variable `email`; use `email_id`.
- Webhook payloads use `{{initial_context.x}}` / `{{gathered_context.x}}` (plain substitution, not Jinja: no filters or indexing); prompts use bare `{{x}}`. QA prompts use single braces `{transcript}`.
- Never invent real UUIDs or URLs. Use `<TOOL_UUID:purpose>`style placeholders and list them.
- Write prompts for speech: short sentences, one question at a time, no lists/markdown/emojis/URLs, name transitions by their exact edge label, and include anti-narration rules in the globalNode plus a one-line guard on risky nodes.
