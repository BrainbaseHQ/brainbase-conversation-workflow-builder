#!/usr/bin/env python3
"""Offline validator for call-assistant workflow_definition JSON.

Mirrors the platform's save-time checks (node types and fields, required
prompts and code, Python syntax of code nodes, edge fields, expression
grammar, graph in/out constraints, instance counts) plus authoring lint
(unreachable nodes, dead ends, codeNode without an always edge, deterministic
edges off LLM nodes, duplicate transition names, {{vars}} without fallback,
network use in code). Stdlib only, makes no network calls.

Usage: python3 validate_workflow.py [--add-positions] [--inputs a,b,c] workflow.json
  --add-positions  first fill in a position for every node missing one
  --inputs a,b,c   inputs that are required on purpose (every call provides
                   them); they no longer warn. Keys in a top-level
                   "template_context_variables" object count as declared too.
Accepts {"nodes": [...], "edges": [...]} or an object that wraps it under
"workflow_definition". Exit 0 = no errors (warnings may still print).

Passing means the JSON will save. It does not prove the conversation design
is good; still review exits, conditions and prompts.
"""
import ast
import json
import re
import sys
from collections import Counter

NODE_FIELDS = {
    "startCall": {"name", "is_start", "is_end", "prompt", "allow_interrupt", "add_global_prompt",
                  "model_overrides", "extraction_enabled", "extraction_prompt", "extraction_variables",
                  "tool_uuids", "document_uuids", "mcp_tool_filters", "greeting", "greeting_type",
                  "greeting_recording_id", "delayed_start", "delayed_start_duration",
                  "pre_call_fetch_enabled", "pre_call_fetch_url", "pre_call_fetch_credential_uuid"},
    "agentNode": {"name", "is_start", "is_end", "prompt", "allow_interrupt", "add_global_prompt",
                  "model_overrides", "extraction_enabled", "extraction_prompt", "extraction_variables",
                  "tool_uuids", "document_uuids", "mcp_tool_filters"},
    "endCall": {"name", "is_start", "is_end", "prompt", "allow_interrupt", "add_global_prompt",
                "model_overrides", "extraction_enabled", "extraction_prompt", "extraction_variables"},
    "globalNode": {"name", "is_start", "is_end", "prompt", "allow_interrupt", "add_global_prompt",
                   "model_overrides"},
    "trigger": {"name", "is_start", "is_end", "trigger_path", "enabled"},
    "webhook": {"name", "is_start", "is_end", "enabled", "http_method", "endpoint_url",
                "credential_uuid", "custom_headers", "payload_template"},
    "qa": {"name", "is_start", "is_end", "qa_enabled", "qa_use_workflow_llm", "qa_provider",
           "qa_model", "qa_api_key", "qa_endpoint", "qa_system_prompt", "qa_min_call_duration",
           "qa_voicemail_calls", "qa_sample_rate"},
    "codeNode": {"name", "is_start", "is_end", "code", "execution_message", "code_timeout"},
    "tuner": {"name", "is_start", "is_end", "tuner_enabled", "tuner_agent_id",
              "tuner_workspace_id", "tuner_api_key"},
}
PROMPT_REQUIRED = {"startCall", "agentNode", "endCall", "globalNode"}
LLM_NODES = {"startCall", "agentNode"}
# (min_in, max_in, min_out, max_out, min_inst, max_inst); None = unbounded
CONSTRAINTS = {
    "startCall": (0, 0, None, None, 1, 1),
    "agentNode": (1, None, None, None, None, None),
    "endCall": (1, None, 0, 0, None, None),
    "globalNode": (0, 0, 0, 0, None, 1),
    "trigger": (0, 0, None, None, None, 1),
    "webhook": (0, 0, 0, 0, None, None),
    "qa": (0, 0, 0, 0, None, None),
    "codeNode": (1, None, 1, None, None, None),
    "tuner": (0, 0, 0, 0, None, 1),
}
EDGE_FIELDS = {"label", "condition", "transition_speech", "transition_speech_type",
               "transition_speech_recording_id", "condition_kind", "expression", "priority"}
ALLOWED_CALLS = {"len", "abs", "min", "max", "sum", "round", "bool", "int", "float", "str",
                 "sorted", "any", "all"}
ALLOWED_AST = (ast.Expression, ast.Constant, ast.Name, ast.Load, ast.Subscript, ast.Attribute,
               ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.UAdd, ast.USub, ast.Not,
               ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
               ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In,
               ast.NotIn, ast.Is, ast.IsNot, ast.IfExp, ast.List, ast.Tuple, ast.Set,
               ast.Dict, ast.Call, ast.Slice) + ((ast.Index,) if hasattr(ast, "Index") else ())
TEMPLATE_VAR = re.compile(r"\{\{\s*([^|\s}]+)(?:\s*\|\s*([^:}]+)(?::([^}]+))?)?\s*\}\}")
UI_ONLY = {"invalid", "validationMessage"}
BUILTIN_VARS = {"caller_number", "called_number", "direction"}
# current_time, current_weekday, or either with an IANA zone (current_time_Europe/Istanbul)
BUILTIN_TIME_VAR = re.compile(r"current_(?:time|weekday)(?:_[A-Z][\w+\-/]*)?")
# an instruction to ask or collect something ("Ask when...", "Thank them and find out...")
ASKING_CLAUSE = re.compile(r"(?:^|,\s*|\b(?:and|then|also|next|first|please|\w+ly|(?:sure|remember|try) to)\s+)"
                           r"(ask|find out|collect|request|check (?:if|whether)|see (?:if|whether))\b", re.I)
NOT_ASKING = re.compile(r"\b(?:not|never|don['’]?t|without|avoid|will|would)\b", re.I)
DECLARED_INPUTS = set()  # filled from --inputs and template_context_variables

errors, warnings = [], []
stripped = Counter()


def err(where, msg):
    errors.append(f"ERROR   {where}: {msg}")


def warn(where, msg):
    warnings.append(f"WARN    {where}: {msg}")


def norm_label(label):
    return re.sub(r"[^a-z0-9]", "_", str(label or "").strip().lower())


def is_builtin(var):
    return var in BUILTIN_VARS or bool(BUILTIN_TIME_VAR.fullmatch(var))


def ending_asks(prompt):
    if "?" in prompt:
        return True
    for sentence in re.split(r"(?<=[.!;])\s+|\n+", prompt):
        sentence = sentence.strip()
        for m in ASKING_CLAUSE.finditer(sentence):
            if not NOT_ASKING.search(sentence[:m.start(1)].rsplit(",", 1)[-1]):
                return True
    return False


def check_expression(where, expr):
    if len(expr) > 2000:
        return err(where, "expression longer than 2000 chars")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return err(where, f"expression syntax error: {e.msg}")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST):
            err(where, f"expression uses disallowed construct {type(node).__name__}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            err(where, f"expression accesses private/dunder name .{node.attr}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_CALLS:
                err(where, "expression calls something other than an allowlisted builtin (no method calls)")
            if node.keywords:
                err(where, "expression call uses keyword arguments")


def main(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    wd = doc.get("workflow_definition", doc) if isinstance(doc, dict) else None
    if isinstance(doc, dict) and isinstance(doc.get("template_context_variables"), dict):
        DECLARED_INPUTS.update(doc["template_context_variables"])
    if not isinstance(wd, dict) or not isinstance(wd.get("nodes"), list) or not isinstance(wd.get("edges"), list):
        err("root", "expected an object with 'nodes' and 'edges' arrays")
        return

    nodes, edges = wd["nodes"], wd["edges"]
    by_id, types = {}, Counter()
    has_global = any(isinstance(x, dict) and x.get("type") == "globalNode" for x in nodes)

    # ---- nodes ----
    for i, n in enumerate(nodes):
        where = f"nodes[{i}]"
        if not isinstance(n, dict):
            err(where, "node must be an object")
            continue
        nid, ntype, data = n.get("id"), n.get("type"), n.get("data")
        if not isinstance(nid, str) or not nid:
            err(where, "missing string id")
            continue
        where = f"node '{nid}'"
        if nid in by_id:
            err(where, "duplicate node id")
        by_id[nid] = n
        if ntype not in NODE_FIELDS:
            err(where, f"unknown node type {ntype!r}")
            continue
        types[ntype] += 1
        pos = n.get("position")
        if not (isinstance(pos, dict) and isinstance(pos.get("x"), (int, float)) and isinstance(pos.get("y"), (int, float))):
            err(where, "missing or invalid position {x: number, y: number}; the workflow saves but fails validation and will not run (fix with --add-positions)")
        if not isinstance(data, dict):
            err(where, "data must be an object")
            continue
        if not isinstance(data.get("name"), str) or not data["name"].strip():
            err(where, "data.name is required")
        for k in data:
            if k not in NODE_FIELDS[ntype] and k not in UI_ONLY:
                stripped[f"{ntype}.data.{k}"] += 1
        if ntype in PROMPT_REQUIRED and not (isinstance(data.get("prompt"), str) and data["prompt"].strip()):
            err(where, f"prompt is required for {ntype}")
        if ntype == "codeNode":
            code = data.get("code")
            if not (isinstance(code, str) and code.strip()):
                err(where, "code is required for codeNode")
            else:
                try:
                    compile(code, nid, "exec")
                except SyntaxError as e:
                    err(where, f"code syntax error line {e.lineno}: {e.msg}")
                if re.search(r"\b(requests|urllib|httpx|socket|aiohttp)\b|\b\w+Factory\s*\(|\bimport\s+\w+Factory\b", code):
                    warn(where, "code appears to import integrations or do network I/O; the sandbox has no network and no integration helpers")
                if re.search(r"\bcontext\[", code):
                    warn(where, "code uses context[...]; use context.get(key, default) so a missing key doesn't raise")
            t = data.get("code_timeout")
            if t is not None and not (isinstance(t, (int, float)) and 1 <= t <= 60):
                err(where, "code_timeout must be 1-60")
        if ntype == "startCall" and data.get("delayed_start_duration") is not None:
            d = data["delayed_start_duration"]
            if not (isinstance(d, (int, float)) and 0.1 <= d <= 10):
                err(where, "delayed_start_duration must be 0.1-10")
        if data.get("model_overrides") is not None:
            mo = data["model_overrides"]
            allowed = {"llm": {"model"}, "tts": {"model", "voice", "language"}, "stt": {"model", "language"}}
            if not isinstance(mo, dict):
                err(where, "model_overrides must be an object")
            else:
                for sect, val in mo.items():
                    if sect not in allowed:
                        err(where, f"model_overrides.{sect} not allowed")
                    elif val is not None:
                        for k in (val or {}):
                            if k not in allowed[sect]:
                                err(where, f"model_overrides.{sect}.{k} not allowed (provider cannot be overridden)")
        for v in data.get("extraction_variables") or []:
            if not isinstance(v, dict) or not v.get("name") or v.get("type") not in ("string", "number", "boolean"):
                err(where, f"bad extraction variable {v!r}: needs name and type string|number|boolean")
            elif not re.fullmatch(r"[a-z][a-z0-9_]*", v["name"]):
                warn(where, f"extraction variable {v['name']!r} should be snake_case")
            elif v["name"] == "email":
                warn(where, "extraction variable named 'email' behaves as reserved; use 'email_id'")
        if data.get("extraction_variables") and not data.get("extraction_enabled"):
            warn(where, "extraction_variables set but extraction_enabled is false; nothing will be extracted")
        if ntype == "endCall" and has_global and not data.get("add_global_prompt", False):
            warn(where, "endCall add_global_prompt defaults to false; set true so the persona/language rules apply to the goodbye (unless intended)")
        if ntype == "webhook":
            if data.get("http_method") not in (None, "GET", "POST", "PUT", "PATCH", "DELETE"):
                err(where, "http_method must be GET|POST|PUT|PATCH|DELETE")
            if data.get("enabled", True) and not data.get("endpoint_url"):
                warn(where, "enabled webhook has no endpoint_url")
            if data.get("payload_template") is not None and not isinstance(data["payload_template"], dict):
                err(where, "payload_template must be a JSON object")
            for h in data.get("custom_headers") or []:
                if not (isinstance(h, dict) and set(h) == {"key", "value"}):
                    err(where, "custom_headers items must be {key, value}")
        if ntype == "trigger" and data.get("trigger_path") is not None:
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,36}", str(data["trigger_path"])):
                err(where, "trigger_path must be 1-36 chars of letters, digits, - or _")
        if ntype == "qa":
            if data.get("qa_sample_rate") is not None and not (isinstance(data["qa_sample_rate"], int) and 1 <= data["qa_sample_rate"] <= 100):
                err(where, "qa_sample_rate must be an integer 1-100")
            if "{{" in str(data.get("qa_system_prompt") or ""):
                warn(where, "qa_system_prompt uses {{double}} braces; QA placeholders are single-brace ({transcript})")

    for t, (_, _, _, _, mn, mx) in CONSTRAINTS.items():
        if mn is not None and types[t] < mn or mx is not None and types[t] > mx:
            want = f"exactly {mn}" if mn == mx else f"at most {mx}"
            err("workflow", f"{want} {t} node(s) allowed (found {types[t]})")

    # ---- edges ----
    in_deg, out_deg = Counter(), Counter()
    out_edges, adj = {}, {}
    seen_edge_ids, seen_pairs = set(), set()
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            err(f"edges[{i}]", "edge must be an object")
            continue
        eid = e.get("id")
        where = f"edge '{eid}'" if eid else f"edges[{i}]"
        if not isinstance(eid, str) or not eid:
            err(where, "missing string id")
        elif eid in seen_edge_ids:
            err(where, "duplicate edge id")
        seen_edge_ids.add(eid)
        src, tgt, data = e.get("source"), e.get("target"), e.get("data")
        for end in (src, tgt):
            if end not in by_id:
                err(where, f"references missing node {end!r}")
        if not isinstance(data, dict):
            err(where, "data must be an object")
            continue
        for k in data:
            if k not in EDGE_FIELDS and k not in UI_ONLY:
                stripped[f"edge.data.{k}"] += 1
        if not (isinstance(data.get("label"), str) and data["label"].strip()):
            err(where, "data.label is required")
        if not (isinstance(data.get("condition"), str) and data["condition"].strip()):
            err(where, "data.condition is required (even on expression/always edges)")
        kind = (data.get("condition_kind") or "llm").strip().lower()
        if kind not in ("llm", "expression", "always"):
            err(where, f"unknown condition_kind {data.get('condition_kind')!r}")
        if kind == "expression":
            if not (isinstance(data.get("expression"), str) and data["expression"].strip()):
                err(where, "expression is required when condition_kind is 'expression'")
            else:
                check_expression(where, data["expression"])
        if data.get("priority") is not None and not isinstance(data["priority"], int):
            err(where, "priority must be an integer")
        if src in by_id and tgt in by_id:
            if (src, tgt) in seen_pairs:
                err(where, f"second route from {src} to {tgt}; only one route is allowed between two steps (the engine keeps one and drops the other). Merge them into one route, or send one outcome to a different step")
            seen_pairs.add((src, tgt))
            out_deg[src] += 1
            in_deg[tgt] += 1
            out_edges.setdefault(src, []).append((where, data, kind))
            adj.setdefault(src, []).append(tgt)

    # ---- per-node graph constraints & lint ----
    for nid, n in by_id.items():
        ntype = n.get("type")
        if ntype not in CONSTRAINTS:
            continue
        mi, ma, mo_, mx, _, _ = CONSTRAINTS[ntype]
        where = f"node '{nid}' ({ntype})"
        if ma is not None and in_deg[nid] > ma:
            err(where, "cannot have incoming edges" if ma == 0 else f"at most {ma} incoming edges")
        if mi is not None and in_deg[nid] < mi:
            err(where, f"needs at least {mi} incoming edge(s)")
        if mx is not None and out_deg[nid] > mx:
            err(where, "cannot have outgoing edges" if mx == 0 else f"at most {mx} outgoing edges")
        if mo_ is not None and out_deg[nid] < mo_:
            err(where, f"needs at least {mo_} outgoing edge(s)")
        if ntype in LLM_NODES and out_deg[nid] == 0:
            warn(where, "no outgoing edges; the conversation can never leave this node")

        outs = out_edges.get(nid, [])
        labels = {norm_label(d.get("label")) for _, d, _ in outs}
        for name, c in Counter(norm_label(d.get("label")) for _, d, _ in outs).items():
            if c > 1:
                err(where, f"two outgoing edges normalize to the same transition name {name!r}; labels must be unique per source node")
        if ntype == "codeNode":
            n_always = sum(1 for _, _, k in outs if k == "always")
            if outs and n_always == 0:
                warn(where, "codeNode has no 'always' default edge; if nothing matches (or the code fails) the call errors out")
            if n_always > 1:
                warn(where, "codeNode has more than one 'always' edge; use exactly one")
            if any(k == "llm" for _, _, k in outs):
                warn(where, "llm edge leaving a codeNode; codeNodes route deterministically (expression/always/__branch__)")
            code = (n.get("data") or {}).get("code") or ""
            for m in re.finditer(r"""outputs\s*\[\s*['"]__branch__['"]\s*\]\s*=\s*['"]([^'"]+)['"]""", code):
                if norm_label(m.group(1)) not in labels:
                    err(where, f"code sets __branch__ = {m.group(1)!r} but no outgoing edge has that label; the call would error")
        else:
            for ew, d, k in outs:
                if k in ("expression", "always"):
                    warn(ew, f"condition_kind '{k}' on an edge leaving a {ntype}; deterministic edges are only evaluated when leaving a codeNode")

    # ---- template variables ----
    required_uses = {}
    for nid, n in by_id.items():
        d = n.get("data") or {}
        for field in ("prompt", "greeting"):
            text = d.get(field)
            if not isinstance(text, str):
                continue
            for m in TEMPLATE_VAR.finditer(text):
                var, fname, fval = m.group(1), m.group(2), m.group(3)
                if fname is not None and fval is not None and fname.strip() != "fallback":
                    err(f"node '{nid}'", f"fallback text in {m.group(0)} contains ':'; only the part before ':' would be used. Write it as {{{{{var} | fallback:{fname.strip()}:{fval.strip()}}}}}")
                if var.startswith("gathered_context"):
                    warn(f"node '{nid}'", f"{{{{{var}}}}} in {field}: extracted values are not visible in prompts; copy them through a codeNode output")
                elif "." not in var and fname is None and not is_builtin(var):
                    required_uses.setdefault(var, []).append(nid)
                if var.split(".")[0] == "email":
                    warn(f"node '{nid}'", "variable 'email' behaves as reserved; use 'email_id'")
                if field == "greeting" and not is_builtin(var):
                    warn(f"node '{nid}'", f"greeting uses {{{{{var}}}}}; the greeting plays before a voicemail can be recognized, so on outbound calls this detail can end up on someone's voicemail. Keep personal details out of the greeting")
        if n.get("type") == "endCall" and ending_asks(str(d.get("prompt") or "")):
            warn(f"node '{nid}'", "ending prompt asks a question or collects something; the call hangs up right after this line, so any answer is lost. Ask in an earlier step")
    for var, where_used in sorted(required_uses.items()):
        if var in DECLARED_INPUTS:
            continue
        warn("input", f"{{{{{var}}}}} has no fallback, so every call must provide it (used in: {', '.join(dict.fromkeys(where_used))}). If that is intended, declare it with --inputs {var}; otherwise add a fallback ({{{{{var} | ...}}}})")

    for key, c in sorted(stripped.items()):
        warn("workflow", f"{key} is not a schema field ({c}x); the server strips it on save, so it has no effect")

    # ---- reachability ----
    start = [nid for nid, n in by_id.items() if n.get("type") == "startCall"]
    if start:
        def reach(origin):
            seen, stack = set(), [origin]
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                stack.extend(adj.get(cur, []))
            return seen
        from_start = reach(start[0])
        for nid, n in by_id.items():
            if n.get("type") in ("agentNode", "endCall", "codeNode") and nid not in from_start:
                warn(f"node '{nid}'", "not reachable from startCall")
        ends = {nid for nid, n in by_id.items() if n.get("type") == "endCall"}
        if not (from_start & ends):
            warn("workflow", "no endCall node is reachable from startCall")
        for nid, n in by_id.items():
            if n.get("type") in ("startCall", "agentNode", "codeNode") and nid in from_start and not (reach(nid) & ends):
                warn(f"node '{nid}'", "no path from this node to any endCall")
        # loops back into an ask step stall on live calls
        depth, queue = {}, [(start[0], 0)]
        while queue:
            cur, d = queue.pop(0)
            if cur not in depth:
                depth[cur] = d
                queue.extend((t, d + 1) for t in adj.get(cur, []))
        for e in edges:
            s_, t_ = e.get("source"), e.get("target")
            if (t_ in depth and s_ in depth and by_id[t_].get("type") in ("startCall", "agentNode")
                    and depth[t_] <= depth[s_] and s_ in reach(t_)):
                warn(f"edge '{e.get('id')}'", f"loops back to ask step '{t_}'; on live calls the agent can ignore the second answer and stall. Use a separate ask step for each attempt")


def add_positions(path):
    """Give every node without a valid position one: x = 400 per step from the
    start, y = 250 per branch. Nodes that already have positions are untouched."""
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    wd = doc.get("workflow_definition", doc)
    nodes = [n for n in wd.get("nodes", []) if isinstance(n, dict)]
    ok = lambda n: isinstance(n.get("position"), dict) and all(isinstance(n["position"].get(k), (int, float)) for k in ("x", "y"))
    missing = [n for n in nodes if not ok(n)]
    if not missing:
        print("all nodes already have positions")
        return
    adj = {}
    for e in wd.get("edges", []):
        adj.setdefault(e.get("source"), []).append(e.get("target"))
    depth = {}
    start = [n["id"] for n in nodes if n.get("type") == "startCall"]
    queue = [(start[0], 0)] if start else []
    while queue:
        cur, d = queue.pop(0)
        if cur in depth:
            continue
        depth[cur] = d
        queue.extend((t, d + 1) for t in adj.get(cur, []))
    taken = {(n["position"]["x"], n["position"]["y"]) for n in nodes if ok(n)}
    off_graph = 0
    for n in missing:
        if n.get("id") in depth:
            x, y = depth[n["id"]] * 400, 0
        else:
            x, y = off_graph * 400, -300
            off_graph += 1
        while (x, y) in taken:
            y += 250
        n["position"] = {"x": x, "y": y}
        taken.add((x, y))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"added positions to {len(missing)} node(s)")


if __name__ == "__main__":
    args = sys.argv[1:]
    fix = "--add-positions" in args
    args = [x for x in args if x != "--add-positions"]
    if "--inputs" in args:
        k = args.index("--inputs")
        if k + 1 >= len(args):
            print(__doc__)
            sys.exit(2)
        DECLARED_INPUTS.update(v.strip() for v in args[k + 1].split(",") if v.strip())
        del args[k:k + 2]
    if len(args) != 1:
        print(__doc__)
        sys.exit(2)
    sys.argv = [sys.argv[0], args[0]]
    if fix:
        add_positions(args[0])
    try:
        main(sys.argv[1])
    except json.JSONDecodeError as e:
        errors.append(f"ERROR   json: invalid JSON at line {e.lineno} col {e.colno}: {e.msg}")
    for line in errors + warnings:
        print(line)
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    sys.exit(1 if errors else 0)
