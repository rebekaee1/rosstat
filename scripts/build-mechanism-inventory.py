#!/usr/bin/env python3
"""Source-derived backend mechanism denominator; no application import or network.

This inventory records syntax and conservative symbol links. It never marks code
reviewed, proves runtime state, evaluates configuration, or replaces contracts.
Only Git tracked/index files participate. Generated outputs and review ledgers
are not inputs, so reviewing this inventory cannot change its own denominator.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = "docs/mechanism-inventory.json"
MD_PATH = "docs/mechanism-inventory.md"
HTTP = {"get", "post", "put", "delete", "patch", "options", "head", "trace", "api_route", "websocket"}
EFFECT_NAMES = {
    "commit", "rollback", "flush", "add", "add_all", "delete", "execute",
    "cache_get", "cache_set", "invalidate_indicator", "bump_namespaces", "versioned_key",
    "get_redis", "get_state_redis", "set", "setex", "incr", "expire", "eval",
    "sadd", "spop", "lpush", "rpush", "xadd", "publish", "create_task", "ensure_future",
    "acquire", "release", "insert", "update", "copy_records_to_table",
}
REGISTRY_HINT = re.compile(r"REGISTRY|SPECS|DEFS|STRATEG|PROVIDER|PASS?PORT|REFERENCES|REDIRECT|SEO|WHITELIST|CODES|TARGETS|CATEGORIES")


def expression(node: ast.AST | None) -> str | None:
    """Preserve unevaluated syntax, including nonliteral/dynamic configuration."""
    return ast.unparse(node) if node is not None else None


def syntax_record(node: ast.AST | None, limit: int = 2000) -> dict:
    """Bound large expressions explicitly; exact source remains hash/line anchored."""
    value = expression(node)
    return {"expression": value if value is None or len(value) <= limit else value[:limit],
            "expression_truncated": value is not None and len(value) > limit,
            "expression_chars": len(value) if value is not None else 0,
            "ast_sha256": hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest() if node is not None else None}


def literal(node: ast.AST | None, fallback=None):
    """Read only Python literals; application expressions never execute."""
    try:
        return ast.literal_eval(node) if node is not None else fallback
    except (ValueError, TypeError):
        return fallback


def keyword(call: ast.Call, name: str) -> ast.AST | None:
    return next((item.value for item in call.keywords if item.arg == name), None)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{dotted(node.value)}.{node.attr}"
    return expression(node) or ""


def module_name(path: str) -> str:
    """Use importable backend module spelling without importing the module."""
    value = path.removeprefix("backend/").removesuffix(".py").replace("/", ".")
    return value.removesuffix(".__init__")


def python_scope(path: str) -> bool:
    return path.endswith(".py") and (
        path.startswith(("backend/app/", "backend/scripts/", "backend/alembic/"))
        or (path.startswith("backend/") and path.count("/") == 1)
        or (path.startswith("scripts/") and path.count("/") == 1
            and not Path(path).name.startswith("test_")
            and path != "scripts/build-mechanism-inventory.py")
    )


def input_paths(root: Path) -> list[str]:
    """Tracked/index implementation and declared runtime data, excluding tests."""
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=root, text=True).split("\0")
    return sorted(path for path in set(paths) if path and (
        python_scope(path)
        or (path.startswith("backend/app/") and path.endswith((".json", ".yaml", ".yml")))
        or path in {"mcp/forecast-analytics-mcp/src/index.ts", "mcp/forecast-analytics-mcp/package.json",
                    "mcp/forecast-analytics-mcp/package-lock.json"}
    ))


def context_map(tree: ast.AST) -> dict[int, dict]:
    """Attach lexical definition and branch conditions to every syntax node."""
    result = {}

    def walk(node: ast.AST, owners: list[str], conditions: list[str]):
        result[id(node)] = {"owner": ".".join(owners) or "<module>", "conditions": list(conditions)}
        nested = owners + [node.name] if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else owners
        for field, value in ast.iter_fields(node):
            children = value if isinstance(value, list) else [value]
            branch = conditions
            if isinstance(node, ast.If) and field in {"body", "orelse"}:
                test = expression(node.test)
                branch = conditions + [test if field == "body" else f"not ({test})"]
            for child in children:
                if isinstance(child, ast.AST):
                    walk(child, nested, branch)

    walk(tree, [], [])
    return result


def alias_map(tree: ast.Module, module: str) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Collect conservative import aliases; collisions remain explicitly ambiguous."""
    candidates: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            prefix = node.module or ""
            if node.level:
                base = module.split(".")[:-node.level]
                prefix = ".".join(base + ([prefix] if prefix else []))
            for item in node.names:
                candidates.setdefault(item.asname or item.name, set()).add(f"{prefix}.{item.name}".strip("."))
        elif isinstance(node, ast.Import):
            for item in node.names:
                candidates.setdefault(item.asname or item.name.split(".")[0], set()).add(item.name if item.asname else item.name.split(".")[0])
    return ({key: next(iter(value)) for key, value in candidates.items() if len(value) == 1},
            {key: sorted(value) for key, value in candidates.items() if len(value) > 1})


def resolve(node: ast.AST, module: str, aliases: dict[str, str]) -> str:
    name = dotted(node)
    first, _, tail = name.partition(".")
    return f"{aliases.get(first, f'{module}.{first}')}{'.' + tail if tail else ''}"


def source_anchor(path: str, node: ast.AST, contexts: dict[int, dict]) -> dict:
    return {"path": path, "line": getattr(node, "lineno", 1),
            "end_line": getattr(node, "end_lineno", 1), **contexts[id(node)]}


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    """Record request/handler parameter annotations/defaults, including Depends."""
    result = []
    positional = node.args.posonlyargs + node.args.args
    defaults = [None] * (len(positional) - len(node.args.defaults)) + node.args.defaults
    for param, default in zip(positional + node.args.kwonlyargs, defaults + node.args.kw_defaults):
        result.append({"name": param.arg, "annotation": expression(param.annotation), "default": expression(default)})
    for param in (node.args.vararg, node.args.kwarg):
        if param:
            result.append({"name": param.arg, "annotation": expression(param.annotation), "variadic": True})
    return {"parameters": result, "returns": expression(node.returns)}


def scan_module(path: str, source: str) -> dict:
    """Extract declarations, references, effects, jobs, and unresolved syntax."""
    tree = ast.parse(source, filename=path)
    module = module_name(path)
    contexts = context_map(tree)
    aliases, ambiguous = alias_map(tree, module)
    local_routers = {target.id for item in ast.walk(tree) if isinstance(item, ast.Assign)
                     and isinstance(item.value, ast.Call) and dotted(item.value.func).split(".")[-1] in {"APIRouter", "FastAPI"}
                     for target in item.targets if isinstance(target, ast.Name)}
    local_handlers = {item.name: item for item in ast.walk(tree) if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
    result = {key: [] for key in ("routers", "router_edges", "route_declarations", "middleware",
              "tables", "settings", "setting_reads", "jobs", "lifecycle", "registries", "registry_mutations",
              "effects", "model_references", "sql", "definitions", "migrations", "unresolved", "environment_reads", "schemas", "registry_references")}
    result["module"] = module
    for key, values in ambiguous.items():
        result["unresolved"].append({"path": path, "kind": "import_alias_collision", "name": key, "candidates": values})
    assignments: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        anchor = source_anchor(path, node, contexts)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            result["definitions"].append({**anchor, "name": node.name, "kind": type(node).__name__})
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            for target in targets:
                if not isinstance(target, ast.Name) or value is None:
                    continue
                if contexts[id(node)]["owner"] == "<module>":
                    assignments[target.id] = value
                if isinstance(value, ast.Call) and dotted(value.func).split(".")[-1] in {"APIRouter", "FastAPI"}:
                    prefix_node = keyword(value, "prefix")
                    prefix = literal(prefix_node, "" if prefix_node is None else None)
                    result["routers"].append({**anchor, "symbol": f"{module}.{target.id}", "type": dotted(value.func),
                                               "prefix": prefix, "constructor": expression(value)})
                    if prefix is None:
                        result["unresolved"].append({**anchor, "kind": "router_dynamic_prefix", "expression": expression(prefix_node)})
                if anchor["owner"] == "<module>" and (target.id.isupper() or REGISTRY_HINT.search(target.id)) and isinstance(value, (ast.Dict, ast.List, ast.Tuple, ast.Set, ast.Call, ast.DictComp, ast.ListComp, ast.SetComp)):
                    keys = [expression(item) or "**unpack" for item in value.keys] if isinstance(value, ast.Dict) else []
                    entries = [{"key": expression(k), **syntax_record(v, 300)} for k, v in zip(value.keys, value.values)] if isinstance(value, ast.Dict) else []
                    result["registries"].append({**anchor, "name": target.id, "symbol": f"{module}.{target.id}",
                         "kind": type(value).__name__, "literal_keys": keys, "entries": entries,
                         **syntax_record(value), "runtime_expansion": isinstance(value, (ast.Call, ast.DictComp, ast.ListComp, ast.SetComp))})
            for target in targets:
                if isinstance(target, ast.Subscript) and dotted(target.value).split(".")[-1].isupper():
                    result["registry_mutations"].append({**anchor, "registry": resolve(target.value, module, aliases), **syntax_record(node)})
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute) or decorator.func.attr not in HTTP:
                    continue
                route = {**source_anchor(path, decorator, contexts), "handler": f"{module}.{anchor['owner'] + '.' if anchor['owner'] != '<module>' else ''}{node.name}",
                         "router": resolve(decorator.func.value, module, aliases),
                         "path_template": literal(decorator.args[0]) if decorator.args else literal(keyword(decorator, "path")),
                         "path_expression": expression(decorator.args[0]) if decorator.args else expression(keyword(decorator, "path")),
                         "methods": [decorator.func.attr.upper()] if decorator.func.attr != "api_route" else literal(keyword(decorator, "methods"), ["GET"]),
                         "options": {item.arg or "**": expression(item.value) for item in decorator.keywords},
                         "handler_line": node.lineno, "handler_end_line": node.end_lineno, **signature(node)}
                result["route_declarations"].append(route)
        if isinstance(node, ast.ClassDef):
            if node.bases:
                result["schemas"].append({**anchor, "name": f"{module}.{node.name}", "bases": [resolve(base, module, aliases) for base in node.bases],
                   "fields": [{**source_anchor(path, field, contexts), "name": dotted(field.target), "annotation": expression(field.annotation),
                               "default": expression(field.value)} for field in node.body if isinstance(field, ast.AnnAssign)]})
            table_node = next((item for item in node.body if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in item.targets)), None)
            if table_node:
                fields, relations, constraints = [], [], []
                for member in node.body:
                    if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name) and isinstance(member.value, ast.Call):
                        call = member.value
                        name = dotted(call.func).split(".")[-1]
                        if name == "mapped_column":
                            options = {kw.arg or "**": expression(kw.value) for kw in call.keywords}
                            args = [expression(arg) for arg in call.args]
                            sql_name = literal(call.args[0]) if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str) else member.target.id
                            optional = "None" in (expression(member.annotation) or "")
                            fields.append({**source_anchor(path, member, contexts), "attribute": member.target.id,
                              "sql_name": sql_name, "annotation": expression(member.annotation), "arguments": args,
                              "options": options, "nullable": literal(keyword(call, "nullable"), optional),
                              "nullable_basis": "explicit" if keyword(call, "nullable") is not None else "Mapped annotation inference (SQLAlchemy runtime not imported)"})
                        elif name == "relationship":
                            relations.append({**source_anchor(path, member, contexts), "attribute": member.target.id,
                                              "annotation": expression(member.annotation), "definition": expression(call)})
                    if isinstance(member, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__table_args__" for t in member.targets):
                        constraints.append({**source_anchor(path, member, contexts), "definition": expression(member.value)})
                result["tables"].append({**anchor, "model": f"{module}.{node.name}", "table": literal(table_node.value),
                                         "bases": [expression(base) for base in node.bases], "fields": fields,
                                         "relationships": relations, "table_constraints": constraints})
            if node.name == "Settings" and path == "backend/app/config.py":
                for member in node.body:
                    if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
                        result["settings"].append({**source_anchor(path, member, contexts), "name": member.target.id,
                          "env_name": "RUSTATS_" + member.target.id.upper(), "annotation": expression(member.annotation),
                          "default": expression(member.value)})
        if isinstance(node, ast.Attribute):
            base = resolve(node.value, module, aliases)
            if base == "app.config.settings" or (path == "backend/app/config.py" and dotted(node.value) == "self"):
                result["setting_reads"].append({**anchor, "name": node.attr, "expression": expression(node)})
            full = resolve(node, module, aliases)
            if full.startswith("app.models."):
                result["model_references"].append({**anchor, "symbol": full, "expression": expression(node)})
        if isinstance(node, ast.Name) and resolve(node, module, aliases).startswith("app.models."):
            result["model_references"].append({**anchor, "symbol": resolve(node, module, aliases), "expression": node.id})
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            result["registry_references"].append({**anchor, "symbol": resolve(node, module, aliases)})
        if not isinstance(node, ast.Call):
            continue
        name = dotted(node.func).split(".")[-1]
        call_ref = resolve(node.func, module, aliases)
        if call_ref in {"os.getenv", "os.environ.get"}:
            result["environment_reads"].append({**anchor, "name": literal(node.args[0]) if node.args else None, **syntax_record(node)})
        if name == "getattr" and len(node.args) >= 2 and resolve(node.args[0], module, aliases) == "app.config.settings":
            result["setting_reads"].append({**anchor, "name": literal(node.args[1]), "expression": expression(node), "dynamic": literal(node.args[1]) is None})
        if name == "include_router" and isinstance(node.func, ast.Attribute) and node.args:
            prefix_node = keyword(node, "prefix")
            result["router_edges"].append({**anchor, "parent": resolve(node.func.value, module, aliases),
               "child": resolve(node.args[0], module, aliases), "prefix": literal(prefix_node, "" if prefix_node is None else None),
               "options": {kw.arg or "**": expression(kw.value) for kw in node.keywords}})
        if name in {"add_api_route", "add_route", "mount", "route"} and isinstance(node.func, ast.Attribute) and dotted(node.func.value) in local_routers:
            if name in {"add_api_route", "add_route"} and len(node.args) >= 2:
                handler = local_handlers.get(dotted(node.args[1]))
                result["route_declarations"].append({**anchor, "handler": resolve(node.args[1], module, aliases),
                  "router": resolve(node.func.value, module, aliases), "path_template": literal(node.args[0]),
                  "path_expression": expression(node.args[0]), "methods": literal(keyword(node,"methods"), ["GET"]),
                  "options": {kw.arg or "**": expression(kw.value) for kw in node.keywords},
                  "handler_line": handler.lineno if handler else None, "handler_end_line": handler.end_lineno if handler else None,
                  **(signature(handler) if handler else {"parameters": [], "returns": None})})
            else:
                result["unresolved"].append({**anchor, "kind": "explicit_or_dynamic_route_registration", "expression": expression(node)})
        if name == "add_middleware":
            result["middleware"].append({**anchor, "application": resolve(node.func.value, module, aliases),
               "class": resolve(node.args[0], module, aliases) if node.args else None,
               "options": {kw.arg or "**": expression(kw.value) for kw in node.keywords}})
        if name == "add_job":
            fn = node.args[0] if node.args else keyword(node, "func")
            assigned = assignments.get(dotted(fn)) if fn else None
            # Assignments inside lifespan also need resolution; retain their source expression.
            if fn and assigned is None and isinstance(fn, ast.Name):
                assigned = next((item.value for item in ast.walk(tree) if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == fn.id for t in item.targets)), None)
            wrapper = fn if isinstance(fn, ast.Call) else assigned
            locked = isinstance(wrapper, ast.Call) and dotted(wrapper.func).split(".")[-1] == "locked_job"
            result["jobs"].append({**anchor, "scheduler": resolve(node.func.value, module, aliases),
              "id": literal(keyword(node, "id")), "callable": expression(fn),
              "resolved_callable": resolve(wrapper.args[0] if locked and wrapper.args else fn, module, aliases) if fn else None,
              "wrapper": expression(wrapper) if assigned is not None or isinstance(fn, ast.Call) else None,
              "lock": {"id_expression": expression(wrapper.args[1]), "ttl_expression": expression(wrapper.args[2]) if len(wrapper.args)>2 else expression(keyword(wrapper, "ttl_seconds"))} if locked else None,
              "options": {kw.arg or "**": expression(kw.value) for kw in node.keywords}})
        if name in {"create_task", "ensure_future", "add_listener", "start", "shutdown", "dispose"}:
            result["lifecycle"].append({**anchor, "call": expression(node), "symbol": call_ref})
        if name in EFFECT_NAMES:
            result["effects"].append({**anchor, "operation": name, "receiver": expression(node.func.value) if isinstance(node.func, ast.Attribute) else None,
                                      "symbol": call_ref, **syntax_record(node)})
        if name in {"append", "extend", "update", "setdefault", "register"} and isinstance(node.func, ast.Attribute):
            receiver = dotted(node.func.value)
            if name == "register" or receiver.split(".")[-1].isupper() or REGISTRY_HINT.search(receiver):
                result["registry_mutations"].append({**anchor, "registry": resolve(node.func.value, module, aliases), "expression": expression(node)})
        if name == "text" and node.args:
            result["sql"].append({**anchor, "literal": literal(node.args[0]), "expression": expression(node.args[0]), "resolved_text_constructor": call_ref})
        if path.startswith("backend/alembic/") and dotted(node.func).startswith("op."):
            result["migrations"].append({**anchor, "operation": name, "definition": expression(node)})
    return result


def compose_routes(routers: list[dict], edges: list[dict], declarations: list[dict]) -> tuple[list[dict], list[dict]]:
    """Compose reachable declared paths from app.main.app, preserving branch gates."""
    router_map = {item["symbol"]: item for item in routers}
    outgoing: dict[str, list[dict]] = {}
    by_router: dict[str, list[dict]] = {}
    for item in edges:
        outgoing.setdefault(item["parent"], []).append(item)
    for item in declarations:
        by_router.setdefault(item["router"], []).append(item)
    routes, unresolved, visited_declarations = [], [], set()

    def walk(symbol: str, prefix: str, mounts: list[dict], ancestors: set[str]):
        if symbol in ancestors:
            unresolved.append({"kind": "router_cycle", "symbol": symbol})
            return
        router = router_map.get(symbol)
        if router is None or router["prefix"] is None:
            unresolved.append({"kind": "unresolved_router", "symbol": symbol, "mounts": mounts})
            return
        combined = prefix + router["prefix"]
        for item in by_router.get(symbol, []):
            visited_declarations.add((item["path"], item["line"]))
            path = item["path_template"]
            if not isinstance(path, str) or not isinstance(item["methods"], list):
                unresolved.append({**item, "kind": "dynamic_route_path_or_methods"})
                continue
            routes.append({**item, "full_path": combined + path, "mounts": mounts,
                           "conditions": [gate for mount in mounts for gate in mount["conditions"]] + item["conditions"]})
        for edge in outgoing.get(symbol, []):
            if edge["prefix"] is None:
                unresolved.append({**edge, "kind": "dynamic_mount_prefix"})
            else:
                walk(edge["child"], combined + edge["prefix"], mounts + [edge], ancestors | {symbol})

    walk("app.main.app", "", [], set())
    for item in declarations:
        if (item["path"], item["line"]) not in visited_declarations:
            unresolved.append({**item, "kind": "unmounted_route_declaration"})
    return routes, unresolved


def mcp_tools(path: str, source: str) -> list[dict]:
    """Parse literal MCP registrations conservatively; this is not a TS parser."""
    starts = list(re.finditer(r'server\.(?:tool|registerTool)\(\s*["\']([^"\']+)["\']', source))
    result = []
    for index, match in enumerate(starts):
        end = starts[index+1].start() if index+1 < len(starts) else len(source)
        block = source[match.start():end]
        calls = []
        for call in re.finditer(r"api\(\s*([`'\"])(.*?)\1(?P<init>,\s*\{[^\n]*?\})?\s*\)", block):
            method_match = re.search(r"method:\s*['\"]([^'\"]+)['\"]", call.group("init") or "")
            calls.append({"method": method_match.group(1) if method_match else "GET", "path_expression": call.group(2),
                          "dynamic": call.group(1) == "`" and "${" in call.group(2)})
        result.append({"path": path, "line": source[:match.start()].count("\n")+1,
                       "end_line": source[:end].count("\n")+1,
                       "schema_line": source[:match.start()].count("\n")+1+block[:block.find("inputSchema")].count("\n"),
                       "handler_line": source[:match.start()].count("\n")+1+block[:block.find("async (")].count("\n"),
                       "name": match.group(1), "api_calls": calls, "source": block.strip(),
                       "parser": "literal registration blocks, unresolved interpolations retained"})
    return result


def build_inventory(root: Path) -> dict:
    """Generate only from independent tracked source; fail closed on parse errors."""
    files, scans, declared_data, mcp = [], [], [], []
    for path in input_paths(root):
        raw = (root / path).read_bytes()
        source = raw.decode("utf-8")
        files.append({"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "lines": len(source.splitlines())})
        if python_scope(path):
            scans.append(scan_module(path, source))
        elif path.endswith("index.ts"):
            mcp = mcp_tools(path, source)
        else:
            value = json.loads(source) if path.endswith(".json") else None
            declared_data.append({"path": path, "format": path.rsplit(".",1)[-1],
                                  "top_level_keys": sorted(value) if isinstance(value, dict) else None,
                                  "meaning": "JSON top-level identity; YAML source is fingerprinted, not semantically parsed"})
    merged = {key: [item for scan in scans for item in scan[key]] for key in scans[0] if key != "module"}
    # Other tools can contain Python fixtures as strings; ast.parse never
    # interprets those strings as declarations or application entrypoints.
    routes, unresolved = compose_routes(merged["routers"], merged["router_edges"], merged["route_declarations"])
    merged["routes"] = routes
    merged["unresolved"].extend(unresolved)
    for middleware in merged["middleware"]:
        middleware["registration_index"] = merged["middleware"].index(middleware) + 1
    model_names = {table["model"] for table in merged["tables"]}
    merged["model_references"] = [item for item in merged["model_references"] if any(item["symbol"] == name or item["symbol"].startswith(name + ".") for name in model_names)]
    registry_symbols = {item["symbol"] for item in merged["registries"]}
    merged["registry_references"] = [item for item in merged["registry_references"] if item["symbol"] in registry_symbols]
    schema_names = {item["name"] for item in merged["schemas"] if "pydantic.BaseModel" in item["bases"]}
    while True:
        extended = schema_names | {item["name"] for item in merged["schemas"] if any(base in schema_names for base in item["bases"])}
        if extended == schema_names:
            break
        schema_names = extended
    merged["schemas"] = [item for item in merged["schemas"] if item["name"] in schema_names]
    return {"schema_version": 1, "scope": "Git tracked/index implementation, current worktree bytes",
      "entrypoint": "app.main.app", "source_files": files, "declarative_data": declared_data,
      **merged, "mcp_tools": mcp,
      "limits": ["Syntax inventory is an independent denominator, not semantic review or deployment proof.",
        "Router paths reflect decorators/includes; framework-generated debug OpenAPI/docs routes are separately declared in FastAPI constructor.",
        "Aliases with collisions, computed mounts and unmounted routes are explicit unresolved records.",
        "ORM nullable inference records Python Mapped annotations, not observed migrated database state; migration operations are listed separately.",
        "Effect names and model references are candidate links; object dispatch, raw SQL, runtime branch configuration and transaction outcome require contracts/read or fixture proof.",
        "Registry comprehensions/builders retain syntax previews, explicit truncation/AST hashes and exact full-source ranges; computed entry cardinality is not evaluated.",
        "Scheduler branch gates/triggers/lock wrappers are source facts; actual enabled process and resource limits belong to ops evidence.",
        "MCP parser reads literal registration blocks only, preserving URL interpolations; no TypeScript evaluation or network."]}


def md_escape(value) -> str:
    return str(value if value is not None else "unresolved").replace("|", "\\|").replace("\n", "<br>")


def markdown(data: dict) -> str:
    """Render complete human indexes with source anchors; JSON retains all detail."""
    lines = ["# Backend mechanism inventory", "", "Независимый синтаксический состав из Git tracked/index исходников. Это знаменатель сверки; смысл и приёмка — в [backend acceptance](code-review/backend-mechanism-acceptance-2026-09-30.md).", "",
      "Полный машинный состав, поля, зависимости, ветвления и выражения — [mechanism-inventory.json](mechanism-inventory.json). Журнал reviews не является входом генератора.", ""]
    for label, key in [("HTTP declarations", "route_declarations"), ("HTTP reachable paths", "routes"), ("ORM tables", "tables"), ("DTO schemas (own fields + resolved inherited bases)", "schemas"), ("Settings fields", "settings"), ("Settings reads", "setting_reads"), ("Direct environment reads", "environment_reads"), ("Jobs", "jobs"), ("Middleware", "middleware"), ("Registry declarations", "registries"), ("Registry references", "registry_references"), ("Migration operations", "migrations"), ("Candidate effects", "effects"), ("Unresolved syntax", "unresolved"), ("MCP tools", "mcp_tools")]:
        lines.append(f"- {label}: **{len(data[key])}**")
    def table(title, headers, rows):
        lines.extend(["", f"## {title}", "", "| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"])
        lines.extend("| " + " | ".join(md_escape(cell) for cell in row) + " |" for row in rows)
    def link(item):
        return f"[{item['path']}:{item['line']}](../{item['path']}#L{item['line']})"
    table("Routes", ["Methods", "Path", "Handler", "Source"],
          [("/".join(row["methods"]), row["full_path"], row["handler"], link(row)) for row in data["routes"]])
    table("Middleware registration (last registered is outermost custom layer)", ["Order", "Class", "Source"],
          [(row["registration_index"], row["class"], link(row)) for row in data["middleware"]])
    for model in data["tables"]:
        table(f"Table `{model['table']}`", ["Python / SQL", "Type", "Nullable", "Column arguments / options", "Source"],
          [(f"{field['attribute']} / {field['sql_name']}", field["annotation"], field["nullable"], str(field["arguments"]) + " " + str(field["options"]), link(field)) for field in model["fields"]])
        lines.extend(["", "Constraints: `" + md_escape(model["table_constraints"]) + "`", "", "Relationships: `" + md_escape(model["relationships"]) + "`"])
    table("Scheduler jobs", ["Job id", "Callable", "Trigger / conditions", "Distributed lock", "Source"],
          [(row["id"], row["resolved_callable"], row["options"].get("trigger", "") + " " + str(row["conditions"]), row["lock"], link(row)) for row in data["jobs"]])
    counts = {}
    for read in data["setting_reads"]:
        counts[read["name"]] = counts.get(read["name"], 0)+1
    table("Settings declarations", ["Environment", "Type / default", "Read sites", "Source"],
          [(row["env_name"], f"{row['annotation']} = {row['default']}", counts.get(row["name"],0), link(row)) for row in data["settings"]])
    table("Registries and declarations", ["Symbol", "Kind", "Literal keys / dynamic expansion", "Source"],
          [(row["symbol"], row["kind"], ", ".join(row["literal_keys"]) or ("computed source expression" if row["runtime_expansion"] else "sequence/source expression"), link(row)) for row in data["registries"]])
    table("MCP tools", ["Name", "HTTP expressions", "Source"], [(row["name"], row["api_calls"], link(row)) for row in data["mcp_tools"]])
    table("Unresolved syntax", ["Kind", "Source / symbol", "Expression"], [(row["kind"], row.get("path", row.get("symbol","")), row.get("expression", row.get("path_expression", row.get("candidates", "")))) for row in data["unresolved"]])
    lines.extend(["", "## Limits", ""] + ["- " + limit for limit in data["limits"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        data = build_inventory(ROOT)
        expected = {JSON_PATH: json.dumps(data, ensure_ascii=False, indent=2) + "\n", MD_PATH: markdown(data)}
        if args.build:
            for path, content in expected.items():
                (ROOT / path).write_text(content)
        else:
            changed = [path for path, content in expected.items() if not (ROOT / path).is_file() or (ROOT / path).read_text() != content]
            if changed:
                print("Mechanism inventory drift: " + ", ".join(changed))
                return 1
        print(json.dumps({key: len(data[key]) for key in ("source_files", "routes", "tables", "settings", "jobs", "unresolved")}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, SyntaxError, subprocess.CalledProcessError) as exc:
        print(f"Mechanism inventory failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
