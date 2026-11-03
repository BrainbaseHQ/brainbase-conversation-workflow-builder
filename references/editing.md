# Editing Existing Workflows

The requester pastes a workflow and asks for a change. Make a **minimal, correct change** that leaves everything else equivalent in meaning.

## Input shapes

- **Bare definition:** `{"nodes": [...], "edges": [...], "viewport": {...}}`.
- **Full saved object:** `{"id": 9, "name": "...", "workflow_definition": {...}, "template_context_variables": {...}, "workflow_configurations": {...}, "call_disposition_codes": {...}, ...}`. Edit inside `workflow_definition`. Return the same shape you were given unless asked otherwise; don't change other top-level keys unless the request is about them.
- **Fragment** (one node or a few edges). Ask for the full workflow if the change touches edges or ids you can't see; otherwise return the edited fragment and say it is a fragment.

## Rules

1. **Preserve ids.** Never rename an existing node or edge id. Webhooks, run logs and other references depend on them. New nodes and edges get new unique ids following the file's existing naming style.
2. **Preserve everything you weren't asked to change:** prompts, existing positions (but every node you add needs one, and if the input has nodes with no position, add them: without positions the workflow won't run; mention it under Heads-up), tool/document/credential UUIDs, extraction variables, model overrides, field order where practical. Don't "improve" unrelated prompts. If you notice an unrelated bug, report it under **Heads-up** and don't fix it unless asked.
3. **Keep the language and voice** of existing prompts. If the workflow is in Turkish, new prompts are in Turkish and match the existing tone and global persona.
4. **Rewire completely.**
   - Inserting a node between A and B: change the A→B edge's `target` to the new node (keep its id, label and condition), then add new-node→B.
   - Deleting a node: remove every edge that touches it, and reconnect its predecessors to a sensible successor so nothing becomes unreachable or a dead end. 
   - Note: an edge id like `e_a_b` may no longer match its endpoints after retargeting. That's fine; ids are stable identifiers, not descriptions.
5. **Keep labels unique per source node** after normalization when adding edges. **Never add a second edge between the same two nodes** (it is silently dropped); merge the conditions into the existing edge instead.
6. **Unknown or UI-only fields** in the input (`measured`, `selected`, `invalid`, `validationMessage`, `wait_for_user_response`, ...) may stay. Don't add new ones. Don't spend the change summary on them.
7. **Always output 2-space indented JSON,** even if the input was minified or indented differently. Keep the existing JSON structure and key order when possible.
8. **Validate before and after.** Run the validator on the input first so you know which errors and warnings already existed. Your output must not add new errors or warnings. The one exception is the greeting warning for a variable that isn't personal, like a per-call `{{company_name}}`, which can't be silenced.
9. **Problems already in the workflow go under Heads-up and aren't fixed.** Describe them in plain words and leave them as they are, including existing validator warnings. Fix one only if the requester asked or the requested change can't work without it. The one exception is missing positions, which you always add (rule 2).
10. **Diff.** Run `scripts/diff_workflows.py before.json after.json` and confirm only the intended things changed.

## Change summary format

Describe what the **call** does differently, in plain language, 1–5 bullets. Don't mention nodes, edges, ids, labels, prompts-as-fields, rewiring or JSON structure; the requester doesn't need them. Use the diff script privately to make sure nothing else changed.

```
What changed
- Before sending the invoice, the agent now asks the caller to confirm their email address.
- The invoice step now uses the confirmed email instead of the one on file.

Heads-up (only if needed)
- This workflow already had a step the caller could never reach (the old billing question). I left it as is; want me to remove it?
```

Bad (too technical): "Added agentNode `confirm_email`; retargeted edge `e_identity_invoice`."
Good: "The agent now confirms the caller's email before sending the invoice."

## Common edit requests

| Request | How |
|---|---|
| "Add a callback option" | Add an endCall (or an agentNode to collect day and time, then an endCall) and an llm edge from every node where a caller might ask for a callback. Add extraction variables for day/time on the collecting node. |
| "Make it deterministic" / "stop the LLM deciding X" | Insert a codeNode after the collecting node, move the decision into Python, replace the LLM edges with expression edges plus one always edge. Make sure the collecting node extracts the input. |
| "Send results to our system" | Add a webhook node (no edges) with `payload_template` built from `{{initial_context.*}}` and `{{gathered_context.*}}`; make sure the needed values are extracted or output by code. Include the outcome (`"steps_reached": "{{gathered_context.nodes_visited}}"`, last item = ending reached) and the contact's number (`{{initial_context.called_number}}` outbound, `{{initial_context.caller_number}}` inbound). |
| "Change the language" | Rewrite every prompt, greeting, transition_speech and execution_message; keep ids, labels and structure. Update `model_overrides` language only if present or asked. |
| "Add a human transfer" | Attach a transfer tool placeholder (`<TOOL_UUID:human_transfer>`) to the relevant nodes' `tool_uuids` and tell the prompt when to use it. There is no transfer node type. |
| "Add a retry" | Add a second ask step (own prompt with the re-ask wording, own extraction variable) and a second check after it: first check's failure goes to the new ask step, second check's success rejoins the main path, its `always` edge goes to a polite exit. Never loop back to the original ask step. If the workflow you were given already loops back, mention it under Heads-up and offer to fix it. |
| "Add voicemail handling" | `detect_voicemail` doesn't exist. Add an llm edge from startCall (condition: a voicemail greeting, beep or automated message answered instead of a live person) to a new ending that leaves a short message with no personal details. Remove personal details from the greeting (it plays before voicemail can be recognized) and move the identity question into the startCall prompt. |
| "Ask X before hanging up" | Endings can't ask anything (the call hangs up right after). Add an agentNode that asks and extracts the answer, route to it instead of the ending, then on to the ending. |
