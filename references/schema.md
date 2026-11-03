# Workflow JSON Schema

Every node type, field, default and graph constraint enforced on save, plus a manual validation checklist. These rules come from the server's save-time behavior; where older public docs or exports disagree, follow this file.

## Top level

```json
{
  "nodes": [ ... ],
  "edges": [ ... ],
  "viewport": {"x": 0, "y": 0, "zoom": 1}
}
```

`nodes` and `edges` are required. `viewport` is optional; leave it out (or keep it unchanged when editing).

The full save body is `{"workflow_definition": {...}, "template_context_variables": {...}, "workflow_configurations": {...}}`. Only produce it when asked.

- `template_context_variables`: flat object of sample `initial_context` values used in editor test calls only (ignored on real calls). Example: `{"first_name": "Ayse", "plan": "premium"}`.
- `workflow_configurations` (all optional): `max_call_duration` (seconds, e.g. 600), `max_user_idle_timeout` (seconds, e.g. 10), `smart_turn_stop_secs` (e.g. 2), `turn_stop_strategy` (e.g. `"turn_analyzer"`), `context_compaction_enabled` (bool), `dictionary` (string of pronunciation/vocabulary hints), `ambient_noise_configuration` (`{"enabled": false, "volume": 0.3}`). Do not invent other keys.

## Node envelope

```json
{"id": "qualify", "type": "agentNode", "position": {"x": 400, "y": 0}, "data": { ... }}
```

| Key | Rule |
|---|---|
| `id` | Required string, unique. Short readable slugs (`start`, `verify_identity`, `end_success`). Never change an existing node's id during an edit. |
| `type` | One of `startCall`, `agentNode`, `endCall`, `globalNode`, `codeNode`, `webhook`, `qa`, `trigger`, `tuner`. Anything else is rejected. |
| `position` | **Required on every node, always.** `{"x": number, "y": number}`. A workflow with any node missing a position saves, but then fails validation and **will not run**. The values don't affect the call: use `x` = 400 × steps from the start, `y` = 250 × branch number, all distinct. `validate_workflow.py --add-positions` fills in any that are missing. |
| `data` | Required object; fields depend on type. **Unknown keys are silently stripped on save.** |

The UI may add top-level `measured`, `selected`, `dragging`, and `data.invalid` / `data.validationMessage`. Harmless; never generate them.

Every node's `data` needs `name` (non-empty; shown on canvas and in call logs). Do not set `is_start` / `is_end`; the type decides that.

## Node types

### startCall (exactly 1; 0 incoming edges)

Entry point. Its prompt drives the first conversational turn.

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | required | |
| `prompt` | string | required, non-empty | System prompt for the opening turn. Supports `{{vars}}`. |
| `greeting_type` | `"text"` \| `"audio"` | `"text"` | |
| `greeting` | string | null | Spoken via TTS the moment the call connects, before the LLM speaks and **before a voicemail can be recognized**. Supports `{{vars}}`, but on outbound calls keep personal details (names, dates, amounts) out of it: they'd be left on a stranger's voicemail. Ask who you're speaking with instead. Empty = LLM opens. Not supported with realtime speech-to-speech models. |
| `greeting_recording_id` | string | null | When `greeting_type` is `"audio"`. Requester-supplied. |
| `allow_interrupt` | bool | false | Caller can barge in. |
| `add_global_prompt` | bool | true | Prepend globalNode prompt. |
| `delayed_start` | bool | false | Wait before speaking after pickup (useful outbound). |
| `delayed_start_duration` | number | 2.0 | 0.1–10 seconds. |
| `extraction_enabled` / `extraction_prompt` / `extraction_variables` | | | See Extraction. |
| `tool_uuids` | string[] | null | Requester-supplied. |
| `document_uuids` | string[] | null | Knowledge base docs. Requester-supplied. |
| `mcp_tool_filters` | | null | Only if present in input or requested. |
| `pre_call_fetch_enabled` | bool | false | POST to a URL before the call; response `{"initial_context": {...}}` merges into context. Voice calls only (not in text-chat tests). |
| `pre_call_fetch_url` | string | null | |
| `pre_call_fetch_credential_uuid` | string | null | |
| `model_overrides` | object | null | See Model overrides. |

### agentNode (≥1 incoming)

One focused conversational step run by the LLM.

Fields: `name`, `prompt` (required), `allow_interrupt` (UI default true; set it explicitly), `add_global_prompt` (true), `extraction_enabled`, `extraction_prompt`, `extraction_variables`, `tool_uuids`, `document_uuids`, `mcp_tool_filters`, `model_overrides`.

### endCall (≥1 incoming, 0 outgoing)

Closes the call: one goodbye turn from its prompt, then hang up immediately. **The caller can't answer anything said here**, so an ending's prompt must never ask a question ("when should we call back?") or collect information; do that in an agentNode before the ending. Use several endings, one per outcome (`end_success`, `end_declined`, `end_callback`), and give each a `name` that states the outcome (it's what gets reported; see "Reporting the outcome" in `authoring-gotchas.md`).

Fields: `name`, `prompt` (required), `add_global_prompt` (**default false for endCall**; set true so persona/language rules apply to the goodbye, which they usually should), `extraction_enabled`, `extraction_prompt`, `extraction_variables`, `model_overrides`. No `allow_interrupt`, no tools.

### globalNode (≤1; no edges)

Persona, tone, language and shared rules prepended to every prompted node whose `add_global_prompt` is true.

Fields: `name`, `prompt` (required). Nothing else needed.

### codeNode (≥1 incoming, ≥1 outgoing)

Runs Python in a sandbox instead of an LLM turn, merges outputs into context, then routes deterministically. Full contract in `routing-context-code.md`.

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | required | |
| `code` | string | required | Valid Python (syntax-checked on save). |
| `execution_message` | string | null | Filler spoken while it runs ("One moment."). |
| `code_timeout` | number | 15 | 1–60 seconds. |

No prompt, no allow_interrupt, no tools.

### webhook (no edges)

Sends one HTTP request after the call completes. Not connected to the graph.

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | required | |
| `enabled` | bool | true | |
| `http_method` | GET POST PUT PATCH DELETE | `"POST"` | |
| `endpoint_url` | string | null | |
| `credential_uuid` | string | null | Applied as Authorization header. |
| `custom_headers` | `[{"key": "...", "value": "..."}]` | null | Values support `{{vars}}`. |
| `payload_template` | object | null | JSON body. String values get simple `{{path}}` substitution (not Jinja: no filters, no indexing, no logic; lists and objects are inserted as JSON text). Available: `{{workflow_run_id}}`, `{{workflow_name}}`, `{{call_time}}`, `{{campaign_id}}`, `{{initial_context.x}}`, `{{gathered_context.x}}`, `{{annotations.x}}`, `{{cost_info.call_duration_seconds}}`, `{{recording_url}}`, `{{user_recording_url}}`, `{{bot_recording_url}}`, `{{transcript_url}}`. Phone numbers: `{{initial_context.caller_number}}` (who dialed; the contact on inbound calls) and `{{initial_context.called_number}}` (who was dialed; the contact on outbound calls); `{{initial_context.direction}}` is `inbound`/`outbound` when set. Outcome: `{{gathered_context.nodes_visited}}` (see `authoring-gotchas.md`). The platform also adds `call_disposition` (technical call status, e.g. completed or hung up) to every payload unless you set that key yourself. |

### qa (no edges)

Post-call LLM quality review.

Fields: `name`, `qa_enabled` (true), `qa_system_prompt` (placeholders `{node_summary}`, `{previous_conversation_summary}`, `{transcript}`, `{metrics}` — **single braces**), `qa_min_call_duration` (int, 15), `qa_voicemail_calls` (false), `qa_sample_rate` (int 1–100, 100), `qa_use_workflow_llm` (true). When that is false: `qa_provider` (openai, azure, openrouter, anthropic), `qa_model`, `qa_api_key`, `qa_endpoint` (Azure only).

### trigger (≤1; 0 incoming)

Exposes public POST endpoints that start an outbound call: `/api/v1/public/agent/<trigger_path>` (published) and `/api/v1/public/agent/test/<trigger_path>` (draft). Body: `phone_number` (required), `initial_context` (optional), `telephony_configuration_id` (optional).

Fields: `name`, `enabled` (true), `trigger_path` (optional; 1–36 chars of letters, digits, `-`, `_`; generated if omitted). Leave it unconnected; the call still begins at startCall.

### tuner (integration; ≤1; no edges)

Post-call export to an observability integration. Fields: `name`, `tuner_enabled`, `tuner_agent_id`, `tuner_workspace_id` (int), `tuner_api_key`. Only add when asked.

## Shared sub-objects

### Extraction (startCall, agentNode, endCall)

Runs an LLM pass over the conversation when the node is left (before the transition), or before hangup on endCall.

```json
"extraction_enabled": true,
"extraction_prompt": "Extract the caller's chosen appointment slot.",
"extraction_variables": [
  {"name": "appointment_date", "type": "string", "prompt": "Date the caller picked, as YYYY-MM-DD"},
  {"name": "wants_reminder", "type": "boolean", "prompt": "True if the caller asked for an SMS reminder"}
]
```

`name` snake_case; `type` is `string`, `number` or `boolean`; `prompt` is the hint. Variables do nothing unless `extraction_enabled` is true.

### Model overrides (startCall, agentNode, endCall)

Only these keys:

```json
"model_overrides": {"llm": {"model": "gpt-4o"}, "tts": {"model": "...", "voice": "...", "language": "tr"}, "stt": {"model": "...", "language": "tr"}}
```

Never include `provider` (rejected). Only add overrides when asked.

## Edge envelope

```json
{"id": "e_start_verify", "source": "start", "target": "verify_identity",
 "data": {"label": "ready", "condition": "The caller confirmed they have a minute to talk."}}
```

| Key | Type | Notes |
|---|---|---|
| `id` | string | Required, unique. Use `e_<source>_<target>`. |
| `source`, `target` | string | Must be existing node ids. |
| `data.label` | string | Required, non-empty. Becomes the LLM transition function name after lowercasing and replacing non-`[a-z0-9]` with `_`, so labels must be unique per source node after that normalization. Also the value `outputs["__branch__"]` matches. |
| `data.condition` | string | Required, non-empty, **even on expression and always edges**. On LLM edges it is the tool description the model reads. |
| `data.transition_speech` | string | Optional line spoken while transitioning. |
| `data.transition_speech_type` | `"text"` \| `"audio"` | Optional. |
| `data.transition_speech_recording_id` | string | Optional, for audio. |
| `data.condition_kind` | `"llm"` \| `"expression"` \| `"always"` | Optional, default `llm`. |
| `data.expression` | string | Required when kind is `expression`. Restricted grammar. |
| `data.priority` | int | Optional; lower evaluated first among deterministic edges. |

## Graph constraints (enforced on save)

| Type | Incoming | Outgoing | Count |
|---|---|---|---|
| startCall | 0 | any | exactly 1 |
| agentNode | ≥1 | any (0 = dead end; avoid) | any |
| endCall | ≥1 | 0 | any |
| codeNode | ≥1 | ≥1 | any |
| globalNode | 0 | 0 | ≤1 |
| webhook, qa | 0 | 0 | any |
| trigger | 0 | any (leave 0) | ≤1 |
| tuner | 0 | 0 | ≤1 |

Cycles are allowed by the schema, but don't use them for retries: a loop back into the same ask step stalls on live calls (use one ask step per attempt; see `authoring-gotchas.md`).

**Only one edge between any two nodes.** The engine identifies edges by their (source, target) pair, so a second edge between the same two nodes is silently dropped. If two outcomes of a step need the same next step, they must share one edge (one condition covering both). See "Code node defaults" in `routing-context-code.md` for what this means for code nodes.

## Fields that do NOT exist

These appear in old docs or exports but are stripped on save: `wait_for_user_response`, `wait_for_user_response_timeout`, `detect_voicemail`, `invalid`, `validationMessage`, `hovered_through_edge`, `selected_through_edge`. Never generate them. If they're in a pasted workflow you may leave them, but never rely on them.

## Manual validation checklist (when you cannot run the validator)

- [ ] Strict JSON parses. Top level has `nodes` and `edges` arrays.
- [ ] Exactly one startCall. At most one globalNode, trigger, tuner.
- [ ] Every node has unique `id`, valid `type`, numeric `position.x/y`, `data.name`.
- [ ] `prompt` non-empty on every startCall, agentNode, endCall, globalNode. `code` non-empty, valid Python on every codeNode.
- [ ] Every `data` key is listed for that type above.
- [ ] Every edge: unique id, source and target exist, non-empty label and condition.
- [ ] Edge counts: startCall 0 in; agentNode ≥1 in; endCall 0 out; codeNode ≥1 in and ≥1 out; globalNode, webhook, qa, trigger, tuner have no edges.
- [ ] Labels unique per source node after normalization. No duplicate (source, target) pairs.
- [ ] Expression edges use the allowed grammar; every codeNode has one `always` edge; no expression/always edges leave a non-code node.
- [ ] Every agentNode and endCall reachable from startCall; every path can reach an endCall.
- [ ] Every `{{var}}` without a `|` fallback is a key the requester will supply (or a built-in). Fallback text containing `:` uses the `{{var | fallback:text}}` form.
- [ ] No ending prompt asks a question. On outbound calls the greeting has no personal details.
