# Requirements Intake

Before writing a new workflow, interview the requester.

## How to ask

- **Five questions, maximum.** Never send more than 5 questions in total for a new workflow, including any follow-up. A detailed request may need 0–2.
- **Fill in first, then ask.** Go through the question bank below and answer everything you can from the request (and from any data, scripts or examples the requester shared). Only what is still unknown **and** would change how the call works is a candidate question.
- **Pick the 5 that matter most**, in this priority order:
  1. Inbound or outbound, and how calls start (only if not obvious).
  2. Required information about each contact (what the agent must know to make the call).
  3. The possible outcomes and what should happen in each.
  4. Safety specifics that can't be defaulted (required disclosures, what the agent must never say, how to verify identity).
  5. Where results should go after the call.
  Everything else gets a sensible default.
- **Defaults instead of questions.** Every unanswered item outside the top 5 gets a default, listed under **Assumptions** in the response so the requester can correct it afterwards.
- **One short message.** Restate the call in 2–3 lines, then a numbered list of at most 5 questions, each with a suggested default in brackets so "yes, defaults" is a valid answer.
- **Plain language.** Ask about the call, not the JSON: no nodes, edges, node types or field names in questions (field names for the requester's own data columns are fine).
- **No question is needed if the request is complete.** Build straight away and list your assumptions.
- **If no one can answer** (unattended, or the requester says "just build it"), proceed with the defaults and list every assumption at the top of the response under **Assumptions**.
- **Edit mode:** ask at most 2 questions, and only ones the requested change raises (e.g. adding a webhook → endpoint; adding a callback → collect a time or just end?).

## Question bank

A checklist for **filling in** the workflow, not a list to send. Answer each item from the request where possible; ask only the top gaps (max 5, see above); default the rest.

### 1. Call basics (required)

- **Direction:** inbound (caller dials in), outbound (agent dials out), or both?
- **Purpose:** what is the one outcome a successful call achieves (book, confirm, qualify, collect payment info, survey, support)?
- **Who is on the other end:** existing customer, lead, patient, vendor? Do they expect the call?

### 2. Agent identity

- **Role/title** the agent should claim (“scheduling assistant”, “account specialist”).

### 3. Opening

- **Fixed greeting or flexible?** Exact opening line if fixed (default: agent name and company, then "who am I speaking with?"; on outbound calls never the contact's name, since the greeting can land on voicemail).

### 4. Conversation flow

- **Knowledge the agent needs:** FAQ, policies, product info → knowledge-base documents? Which questions must it refuse to answer?
- **Tools during the call:** transfer to a human (to what number/queue?), look up or update a record, send an SMS, book in a calendar? (→ tool placeholders.)

### 5. Data to capture (outputs)

- **What to record** from each call (decision, new time, reason for decline, callback time, satisfaction score…) with type: text, number, yes/no.
- **Outcomes / dispositions:** the list of distinct endings (e.g. confirmed, rescheduled, declined, callback, wrong number, unverified, voicemail). Each becomes its own ending, named after the outcome, and is reported to the webhook automatically. Does the receiving system need one plain outcome field, or is the list of steps reached fine? (default: list of steps)

### 6. After the call

- **Send results somewhere?** Endpoint URL, method, auth/credential, headers, and the exact payload fields wanted.

### 7. Safeties and compliance

- **Never-say / never-do:** no medical, legal or financial advice; no prices or promises beyond X; never reveal details before identity is verified; never ask for card numbers, SSNs or passwords.
- **Opt-out / do-not-call:** what to do when the caller says “stop calling me.”
- **Escalation:** when to hand off to a human (anger, distress, legal threats, request for a manager), and how (transfer tool or callback promise).
- **Voicemail:** leave a message (what?), or hang up?
- **Calling hours / retries:** usually handled outside the workflow; note them if given.

### 8. Call limits (optional)

- Max call length (default 600 s), silence timeout before the agent checks in or ends (default 10 s), and whether long calls should compact context. (→ `workflow_configurations`; only output if the requester asks for the full save body.)

## Mapping answers to the workflow

| Answer | Goes into |
| --- | --- |
| Agent name, company, tone, language, AI disclosure, never-say rules, opt-out, off-topic handling | `globalNode` prompt (+ one-line guards on risky nodes) |
| Fixed opening line | `startCall.greeting` |
| Identity check and attempts | one ask step + one code check **per attempt** (no loop back); last check's `always` edge → polite unverified ending |
| Required inputs | bare `{{var}}`; list under “Required inputs” |
| Optional inputs | `{{var \| fallback}}`; list under “Optional inputs” |
| Inputs only read in code (e.g. a ZIP code that's checked but never spoken) | `context.get` in the `codeNode`; still list them, since no prompt shows they're needed |
| Pre-call lookup | `startCall.pre_call_fetch_*` |
| Each caller answer at each step | one llm edge with a specific condition |
| Exact rules | `codeNode` + expression edges |
| Transfer / lookup / SMS tools | `tool_uuids` placeholders + prompt says when to use them |
| Data to capture | `extraction_variables` or code `outputs` |
| Outcomes | one `endCall` per outcome, named after it; webhook sends `{{gathered_context.nodes_visited}}` (or an outcome-stamp codeNode per ending if a single field is needed) |
| Contact's phone number in results | webhook: `{{initial_context.called_number}}` (outbound) / `{{initial_context.caller_number}}` (inbound) |
| Results destination | `webhook` |
| QA wishes | `qa` node |
| Must-read disclosures | dedicated step with `allow_interrupt: false` |
| Outbound | `delayed_start: true`, 1–2 s; **always** a voicemail branch from startCall to a neutral voicemail ending; no personal details in the greeting |
| API-started outbound | `trigger` node (unconnected) |

## Message template

```
Here's how I understand the call: <2–3 lines>.

A few quick questions before I build it (suggested answer in brackets; reply "defaults" to accept all):

1. <highest-priority gap> [default]
2. ...
(5 at most)

Everything else I'll set to sensible defaults and list them with the workflow so you can change them.
```
