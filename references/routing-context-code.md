# Routing, Context and Code Nodes

How calls move through the graph, edge kinds, the code node contract, the expression grammar, and which variables are visible where.

## How a call moves through the graph

1. The call starts at **startCall**. If `greeting` is set it is spoken first, then the LLM runs with the startCall prompt (plus the global prompt if `add_global_prompt` is true).
2. At every **startCall** and **agentNode**, each outgoing edge with `condition_kind` `llm` (or unset) is registered as a tool for the LLM. Tool name = normalized label; tool description = condition. The model calls one when it judges the condition met. **That is the only way an LLM node moves on.**
3. When a node is left: its extraction runs (if enabled), then the edge's `transition_speech` plays (if set), then the target node starts.
4. A **codeNode** is not an LLM turn. When reached it waits for pending extraction, speaks `execution_message` if set, runs `code`, merges `outputs` into context, picks an edge deterministically (rules below) and immediately advances.
5. An **endCall** runs one closing LLM turn with its prompt, runs extraction if enabled, then hangs up.
6. After the call, **webhook**, **qa**, **tuner** nodes run. They are not on the graph.

Consequences:

- An LLM node with no outgoing edges can never move on. The call stalls until the caller hangs up or max duration is hit.
- `expression` and `always` edges leaving an LLM node are invisible to the model and never evaluated. Deterministic branching must leave from a codeNode.
- To branch on something the caller said: LLM node → codeNode → expression edges. Extraction on the LLM node captures the value as it is left; the codeNode then sees it.

## Edge kinds

| condition_kind | Chosen by | Valid leaving | Notes |
|---|---|---|---|
| `llm` (default) | The LLM, via the transition tool | startCall, agentNode | Write `condition` as an observable fact about the conversation. |
| `expression` | Boolean expression over context | codeNode only | First truthy one in (priority, edge order) wins. A missing variable makes it false, not an error. |
| `always` | Default / else | codeNode only | Exactly one per codeNode. |

## Code node edge selection order

1. If code set `outputs["__branch__"] = "<label>"`, take the edge with that label (case-insensitive, trimmed). If no edge has that label, **the call errors**. Only use `__branch__` with labels that exist.
2. Else evaluate expression edges sorted by `priority` (lower first; ties keep array order). First truthy wins.
3. Else take the `always` edge. If none, the first non-expression edge.
4. Else the call errors (no route). So always add an `always` edge.

If the code raises or times out, the error goes into `__code_error__` and the node routes via the `always` edge.

### Code node defaults (the `always` edge)

- **Normally:** make the `always` edge the **safe exit** (hand off to a human, or apologize and end), not the happy path. Success and other outcomes use `expression` edges.
- **When that's impossible:** only one edge is allowed between two nodes. If the safe exit would go to the same next step as another outcome, or the flow has no separate safe step, then the shared route has to be the `always` edge, even if it's the normal path. In that case make the code itself fail safe:
  1. Wrap the whole body in `try: ... except Exception: ...` so it never raises.
  2. Set every flag to its **safe value first** (`outputs['ok'] = False`) and only flip it after the check passes.
  3. Route the risky outcome (e.g. "verified, share the details") with an `expression` edge on an explicit flag, so a failed or skipped check can never take it.
  4. Make sure the step the `always` edge leads to behaves sensibly even if the check didn't run.
- Or add a separate step for the safe exit (its own ending, or a short "let me have someone call you back" step) so the `always` edge has its own target.

## Expression grammar (restricted, checked on save)

**Allowed:** names from context; literals (numbers, strings, `True`/`False`/`None`, list/tuple/set/dict literals); `and or not`; comparisons `== != < <= > >= in not in is is not`; `+ - * / // %`; unary `+ -`; `x if c else y`; subscripts `ctx["k"]`; dotted access as dict lookup (`gathered_context.city`); calls to only `len abs min max sum round bool int float str sorted any all` (positional args only).

**Rejected:** `**`, bit operators, lambdas, comprehensions, imports, method calls (`name.lower()`), attribute names starting with `_`, any other function. Max 2000 chars.

- Good: `is_verified and not is_blocked`, `status in ("active", "pending")`, `int(birth_year) == int(expected_year)`, `len(missing_fields) == 0`.
- Bad: `name.lower() == "yes"` (method call), `x ** 2 > 4`, `re.match(...)`. Do that work in the code and expose a boolean.

**Simplest reliable pattern:** do the logic in Python, set boolean flags in `outputs`, and make each expression a single flag name (`is_refundable`).

## Code node contract

```python
# `context` is a dict: flat view of initial_context plus everything gathered so far
# (extracted variables, earlier code outputs). Gathered values win on name conflicts.
# Nested views: context["initial_context"], context["gathered_context"].
year = str(context.get("birth_year_said", "")).strip()
expected = str(context.get("birth_year", "")).strip()
outputs["identity_ok"] = bool(year) and year == expected
```

Rules:

- Read with `context.get(key, default)`. Never `context[key]` for values that may be missing; a KeyError routes you to the default edge.
- Write results only into `outputs` (a dict, reset each run). Keys starting with `__` are not merged except `__branch__` (routing). Keys `gathered_context`, `initial_context`, `extracted_variables`, `nodes_visited` are protected and ignored.
- Every `outputs` key is merged into live context. Later prompts can use it as `{{key}}`, later code reads `context["key"]`, webhooks use `{{gathered_context.key}}`. Output size cap 256 KB.
- Python globals persist across code nodes in the same call, but rely on outputs/context for anything that matters.
- **Standard library only. No third-party packages. No network.** The sandbox has no internet and no DNS, and no managed integration helpers. Code that fetches a URL or imports an integration fails and leaves outputs empty. External data must come in through `initial_context` (campaign CSV, API trigger), `pre_call_fetch_url`, or an HTTP tool attached to an LLM node.
- Keep it fast; the caller hears silence while it runs. Use `execution_message` if not trivial; keep `code_timeout` at 15 or lower.
- Code must be valid Python (syntax-checked on save). In JSON it is one string with `\n` newlines and escaped quotes. Prefer single quotes inside code.
- LLM-extracted values come back as the declared type when possible, but be defensive: `str(...).strip()`, `int(...)` inside try/except, `.lower()` for comparisons.

## Variables: what is visible where

| Source | Prompt `{{x}}` (startCall/agent/endCall and the shared persona prompt) | codeNode context | Edge expression | Webhook payload |
|---|---|---|---|---|
| `initial_context` (CSV columns, API trigger body, test context vars) | yes, `{{x}}` and nested `{{a.b}}` | yes | yes | `{{initial_context.x}}` |
| Pre-call fetch response | yes | yes | yes | `{{initial_context.x}}` |
| Built-ins: `{{current_time}}`, `{{current_weekday}}`, `{{current_time_Europe/Istanbul}}`, `{{current_weekday_<IANA tz>}}` | yes | no | no | no |
| Phone numbers and direction (stored in `initial_context`): `caller_number` (who dialed), `called_number` (who was dialed), `direction` | yes, `{{caller_number}}` | yes | yes | `{{initial_context.caller_number}}`, `{{initial_context.called_number}}` |
| Steps reached, in order (`nodes_visited`, by step name) | no | no | no | `{{gathered_context.nodes_visited}}` |
| Extracted variables | **no** | yes | yes | `{{gathered_context.x}}` |
| codeNode outputs | yes (`{{x}}` from the next node on) | yes | yes | `{{gathered_context.x}}` |

**Key consequence:** an extracted value cannot be used directly in a later prompt. If a later prompt must say something the caller gave earlier ("I have you down for {{appointment_time}}"), route through a codeNode that copies it: `outputs["appointment_time"] = context.get("appointment_time", "")`. Otherwise let the LLM remember it from conversation history, which it has.

## Template syntax

- `{{name}}` substitutes; nested `{{user.name}}` works.
- Fallback: `{{name | there}}` is used when the value is missing or empty. **If the fallback text contains a colon** (times like `5:30`, "Note: ..."), write it as `{{name | fallback:text with: colons}}`; in the short form everything from the first `:` on is dropped. Fallback text can't contain `}`.
- **The shared persona prompt (globalNode) supports `{{variables}}` exactly like node prompts**: it's rendered with the same values each time it's added to a node.
- Every `{{var}}` without a fallback and without a dot is treated as a **required input**. For campaigns that means a required, non-empty CSV column for every row. Give optional fields a fallback or read them in a codeNode.
- Don't use `email` as a variable or CSV column name; it behaves as reserved. Use `email_id`.
- Webhook payload strings use the same simple `{{path}}` substitution (not Jinja: no filters, indexing or logic) over `initial_context`, `gathered_context`, `annotations`, `workflow_run_id`, `cost_info`, and recording/transcript URLs. Lists and objects are inserted as JSON text.
- QA prompts use single-brace placeholders: `{transcript}`, `{node_summary}`, `{previous_conversation_summary}`, `{metrics}`.

## Tools and knowledge base on LLM nodes

- `tool_uuids` attaches platform tools (HTTP API, end call, call transfer, MCP, python, calculator). The LLM decides when to call them from the tool's description plus your prompt, so the node prompt should say when to use each ("If the caller asks for a human, use the transfer tool.").
- HTTP tools run on the server, so they can reach the internet even though code nodes cannot. They do not follow redirects.
- `document_uuids` adds a knowledge base retrieval tool. Tell the prompt when to consult it.
- You never know real UUIDs. Use `"<TOOL_UUID:short_purpose>"` / `"<DOCUMENT_UUID:short_purpose>"` placeholders and list them.
- Attach only the tools a node needs. Fewer tools = more reliable calls.
- A transfer or end-call tool ends the conversation without an endCall node. That's fine, but every graph should still have endCall nodes for the normal outcomes.
- There is no transfer node type; transfers are tools.
