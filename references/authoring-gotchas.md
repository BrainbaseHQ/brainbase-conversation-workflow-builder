# Authoring Patterns and Gotchas

Graph design, voice prompt writing, edge conditions, and production failures already seen.

## Graph design

- **One job per node.** A node asks for or delivers one thing (confirm availability, verify identity, explain the offer, collect a callback time). If a prompt has three unrelated goals, split it.
- **Every LLM node needs an exit for each realistic caller answer.** For a yes/no step that's usually: yes, no, wants a callback, wrong person, not interested or hostile. Missing exits are the most common cause of looping or stalling.
- **Separate endCall nodes per outcome** (`end_success`, `end_declined`, `end_callback`, `end_wrong_person`). Name each one after its outcome; that name is how the outcome gets reported (below).
- **Endings only say goodbye.** The call hangs up right after an ending's line, so an ending must never ask a question or collect anything. If the outcome needs information (a callback time, a reason), collect it in an agentNode with extraction first, then go to the ending.
- **Use a globalNode** for persona, language, tone, and rules that apply everywhere (never read lists aloud, never mention you're following instructions, how to handle "are you a robot?", what to do with off-topic questions). Keep node prompts focused on their step. Set `add_global_prompt: true` on every prompted node **including endCall nodes** (whose default is false), unless a node must not get the persona.
- **Deterministic decisions go through a codeNode.** Matching an ID number, checking a birth year, counting retries, computing a price, choosing a branch from CSV data: the LLM collects the input, the code decides. LLMs are unreliable at comparing digits.
- **Retries: one ask step per attempt, never a loop back.** When an answer must be re-asked (wrong birth year, unclear account number), give each attempt its own agentNode and its own check: ask → check → (fail) ask again → check again → (fail) polite exit. Do **not** route a failed check back to the same ask step; on live calls the agent often ignores the second answer and stalls, and a re-ask line on the transition only fixes it sometimes. Put the re-ask wording ("That didn't match, could you say it once more?") in the second ask step's prompt, give it its own extraction variable (e.g. `birth_year_said_retry`), and cap attempts at 2–3. See `examples/appointment_confirmation.json`.
- **Bring data in before the call**, not during it: campaign CSV columns or the API trigger's `initial_context` for per-contact data; `pre_call_fetch_url` for lookups on inbound calls. Code nodes cannot fetch.
- **Return data after the call** with a webhook whose `payload_template` uses `{{initial_context.x}}` and `{{gathered_context.x}}`. Put the fields you need downstream into extraction variables or code outputs so they land in `gathered_context`.

## Reporting the outcome

The ending a call reaches **is** its outcome. Report it deterministically; don't ask the AI to fill in an "outcome" value at each ending.

- **Default (no extra steps):** send `"steps_reached": "{{gathered_context.nodes_visited}}"` in the webhook payload. The platform records the name of every step the call enters, in order, so the **last item is the ending reached** (or, if the caller hung up early, the step they dropped at). Give endings outcome names (`Confirmed`, `Callback Requested`, `Wrong Person`) so the receiving system can read the last item directly. The value arrives as JSON text, e.g. `["Opening", "Ask Birth Year", "Confirmed"]`.
- **When the receiver needs one plain outcome field:** put a tiny codeNode in front of each ending that stamps it, e.g. `outputs['call_outcome'] = 'callback_requested'`, with one `always` edge to the ending; send `"outcome": "{{gathered_context.call_outcome}}"`. Fully deterministic, at the cost of one extra step per ending. Calls that end before reaching any ending (caller hangs up) send an empty value.
- **When the requester asks for an "outcome" field:** use the codeNode stamp above, because webhook payloads can't index into `nodes_visited` to pull out the last item. Send `steps_reached` as well, so calls that end early still show where they stopped.
- `call_disposition`, which the platform adds to every webhook automatically, is the **technical** call status (completed, hung up, ...), not the business outcome.

## Voicemail (outbound calls)

- Every outbound workflow gets a voicemail branch: an llm edge from startCall (condition: a voicemail greeting, beep or automated message answered instead of a live person) to an ending that leaves a short, neutral message. `detect_voicemail` doesn't exist; this branch is how voicemail is handled.
- **The greeting plays before a voicemail can be recognized.** On outbound calls keep personal details out of it (no names, dates, amounts): greet, say who's calling, and ask who you're speaking with. Confirm identity in the startCall prompt, after a live person answers.
- **When the greeting asks who's speaking, add this line to the startCall prompt:** "If the answer is unclear, ask for their name. Never mention the account before identity is confirmed." (Swap "account" for what the call is about.) Let it re-ask only twice, then route to a polite ending if the answer is still unclear. Without this line, a caller who just says "yes" can trip the step, and the agent may start on the account before checking who it is.
- **Company name that changes per call:** use `{{company_name}}` in the greeting and declare it with `--inputs company_name`. A company name isn't a personal detail, so it's safe on a voicemail; the validator's greeting warning still prints for it and can be left.
- The voicemail message itself must not include personal details either.

## Prompt writing for voice

- Write for speech: short sentences, one question at a time, no markdown, no bullet lists, no emojis, no URLs read aloud.
- Spell out how to say numbers, money, dates, phone numbers and IDs in the caller's language (e.g. phone numbers in groups).
- When a prompt names a transition, use the edge's **exact label**. Tell the node exactly when to transition: "As soon as the caller confirms, move on using the 'confirmed' transition. Do not say anything else before transitioning." This prevents filler before a transition.
- Tell the model not to narrate its reasoning or mention tools, nodes, transitions or instructions. Put this in the globalNode **and** repeat a one-line guard in the highest-risk nodes (identity checks, closings). A global rule alone wasn't enough in production.
- For legal/compliance text that must be read in full, set `allow_interrupt: false` on that node; otherwise use true.
- Greeting: use `greeting` for a fixed opener (fast, consistent). Leave it empty if the LLM must adapt the opener. On outbound calls, no personal details in it (see Voicemail).
- Outbound calls: consider `delayed_start: true` with `delayed_start_duration` 1–2 so the agent doesn't talk over "hello?".
- Match the caller's language everywhere: global prompt, node prompts, greeting, transition_speech, execution_message. JSON keys, ids and labels stay ASCII snake_case English.

## Edge conditions

- Write conditions as observable facts: "The caller said they are not interested and does not want a callback." Not "not interested".
- Make sibling conditions mutually exclusive. If two can both be true, the model picks arbitrarily.
- Labels: short, ASCII, unique per source node (`confirmed`, `declined`, `callback`, `wrong_person`). They become function names.
- `transition_speech` is optional; use it for a short bridge ("Great, one moment.") only when the next node doesn't open with its own line, otherwise the caller hears two lines back to back.

## Known failures from production (do not repeat)

| Failure | Fix |
|---|---|
| Builders made the AI fill in an outcome value at every ending; it wasn't reliable. | Report the ending reached via `{{gathered_context.nodes_visited}}`, or stamp it with a codeNode before each ending (see Reporting the outcome). |
| An ending asked "when's a better time?" but the call hung up right after, so the answer was lost. | Endings never ask questions; collect the answer in an agentNode first. |
| Greeting with the contact's name played into a voicemail. | No personal details in outbound greetings; voicemail branch from startCall. |
| Fallback text with a colon (`{{time \| 5:30 pm}}`) rendered as "5". | Use `{{time \| fallback:5:30 pm}}`. |
| Two edges between the same two steps; one silently disappeared. | One edge per pair: merge the conditions, or send one outcome elsewhere. |
| Retry loop sent a failed answer back to the same ask step; the agent ignored the second answer and stalled. A re-ask line on the transition fixed it only some of the time. | Separate ask step (and check) for each attempt. The validator warns on loop-backs into ask steps. |
| Workflow without node positions saved, then failed validation and would not run. | Every node needs a `position`. Run `validate_workflow.py --add-positions` (or follow the rule in `schema.md`). |
| Expression edges off an LLM node never fire. | Deterministic edges are only evaluated when leaving a codeNode. Insert a codeNode. |
| `{{var}}` without fallback became a required CSV column; campaign uploads failed or rows were rejected. | Give optional variables a real fallback word (`{{plan \| current}}`) or read them in a codeNode. |
| `email` column name misbehaved. | Use `email_id`. |
| Code node imported a managed integration helper from another agent platform. It doesn't exist here; outputs were silently empty and the agent hit its "no data" fallback. | Pass data in via `initial_context` or pre-call fetch, parse it in code. |
| Code node tried `urllib` / `requests`. Sandbox has no DNS. | Same as above. |
| Pre-call fetch / tools pointed at a Google Apps Script `/exec` URL. The platform doesn't follow redirects; Apps Script answers 302, so the body is lost. | Apps Script works as a webhook target (the POST runs before the redirect) but not as a data source. |
| Agent spoke its reasoning aloud ("Now I will verify the identity..."). | Global anti-narration rule plus local guards on risky nodes. |
| Fields from old docs (`wait_for_user_response`, `detect_voicemail`) were set and silently dropped. | They don't exist. Don't generate them. |
| Copying a workflow doesn't copy its LLM model. | Out of scope for the JSON, but tell the requester to set the model on the copy when cloning. |
| Pre-call fetch doesn't run in text-chat tests. | Tell the requester to supply the same keys as test context variables (`template_context_variables`) for text testing. |

## Before you hand it over

Run the validator. Then reread every LLM node and ask: what are all the things a real caller might say here, and does each one have an edge? Then reread every codeNode and ask: what if every `context.get` returns the default?
