"""Read and assess explicitly selected hardware module manifests."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from project_library import file_hash, identifier, linked_path, selected_file

SCHEMA = "hardware-module-pack-v1"
SLOTS = ("saved_eda", "calculation", "simulation", "bench")
DIRECTIONS = ("input", "output", "bidirectional", "passive")
DISTRIBUTIONS = {"public-original", "private", "reference-only"}
# The corresponding kinds from hardware's engineering policy, for standalone use.
CHANGE_KINDS = (
    "part", "production-config", "pin-pad", "filter", "power", "layout", "firmware",
    "supplier", "price-stock", "bom-variant", "test-fixture", "process", "assembly-process", "unknown",
)
FIT_ORDER = {"fits": 0, "needs_input": 1, "recheck": 2, "blocked": 3}
UNKNOWN_LICENSES = {"unknown", "unlicensed", "noassertion", "none", "reference-only"}


def read_json(raw):
    def unique_keys(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"invalid JSON number: {value}")
        return number

    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_keys, parse_float=finite, parse_constant=finite)


def fields(value, label, required=(), optional=()):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    missing = set(required) - value.keys()
    extra = value.keys() - set(required) - set(optional)
    if missing or extra:
        raise ValueError(f"{label}: missing={sorted(missing)}, unknown={sorted(extra)}")
    return value


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")


def array(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def object_map(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object keyed by identifiers")
    for key in value:
        identifier(key)
    return value.items()


def unique(values, label):
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def number(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def domain(value, label, required=(), optional=(), *, predicate=False):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    if predicate and "equals" in value:
        fields(value, label, (*required, "equals"), optional)
        nonempty(value["equals"], f"{label}.equals")
    elif not predicate and "enum" in value:
        fields(value, label, (*required, "enum"), optional)
        items = array(value["enum"], f"{label}.enum")
        if not items:
            raise ValueError(f"{label}.enum must contain a value")
        for item in items:
            nonempty(item, f"{label}.enum")
        unique(items, f"{label}.enum")
    else:
        fields(value, label, (*required, "unit", "min", "max"), optional)
        nonempty(value["unit"], f"{label}.unit")
        low, high = value["min"], value["max"]
        if not number(low) or not number(high) or low > high:
            raise ValueError(f"{label} requires finite, ordered inclusive bounds")


def predicates(value, label, declared):
    for key, rule in object_map(value, label):
        if key not in declared:
            raise ValueError(f"{label} has an undeclared condition: {key}")
        domain(rule, f"{label}.{key}", predicate=True)
        condition = declared[key]
        if rule.get("unit") != condition.get("unit"):
            raise ValueError(f"{label}.{key} has a different condition type or unit")


def string_refs(value, label, known=None):
    items = array(value, label)
    for item in items:
        identifier(item)
        if known is not None and item not in known:
            raise ValueError(f"{label} has an unknown reference: {item}")
    unique(items, label)


def validate_interfaces(items, *, manifest):
    interface_ids = []
    for item in array(items, "interfaces"):
        description = ("role", "direction", "reference_domain")
        required = ("id", *description, "mapping") if manifest else ("id",)
        fields(item, "interface", required, () if manifest else description)
        interface_ids.append(identifier(item["id"]))
        for key in ("role", "reference_domain"):
            if key in item:
                nonempty(item[key], f"interface.{key}")
        if "direction" in item and item["direction"] not in DIRECTIONS:
            raise ValueError("interface.direction has an unknown value")
        if manifest:
            mapping = fields(item["mapping"], "interface.mapping", optional=("pin", "net"))
            if not mapping:
                raise ValueError("interface.mapping requires a pin or net")
            for key, value in mapping.items():
                nonempty(value, f"interface.mapping.{key}")
    unique(interface_ids, "interface ids")


def validate_manifest(data):
    fields(data, "manifest", (
        "schema", "module_id", "revision", "variant", "function", "tags", "scope",
        "provenance", "interfaces", "conditions", "parts", "files", "evidence",
    ), ("allowed_changes", "forbidden_combinations", "layout_constraints", "change_impact"))
    if data["schema"] != SCHEMA:
        raise ValueError("unknown module manifest schema")
    for key in ("module_id", "revision", "variant"):
        identifier(data[key])
    for key in ("function", "scope"):
        nonempty(data[key], key)
    for tag in array(data["tags"], "tags"):
        nonempty(tag, "tag")
    unique(data["tags"], "tags")

    provenance = fields(data["provenance"], "provenance", ("kind", "sources", "license", "distribution"))
    for key in ("kind", "license", "distribution"):
        nonempty(provenance[key], f"provenance.{key}")
    distribution = provenance["distribution"]
    if distribution not in DISTRIBUTIONS:
        raise ValueError("provenance.distribution has an unknown value")
    if distribution == "public-original" and provenance["kind"] != "original":
        raise ValueError("public-original requires original provenance")
    if distribution != "reference-only" and provenance["license"].strip().casefold() in UNKNOWN_LICENSES:
        raise ValueError("unknown module license requires reference-only distribution")
    sources = array(provenance["sources"], "provenance.sources")
    if provenance["kind"] != "original" and not sources:
        raise ValueError("non-original provenance requires a source")
    for source in sources:
        fields(source, "source", ("locator", "use"), ("revision", "detail"))
        for key, value in source.items():
            nonempty(value, f"source.{key}")

    validate_interfaces(data["interfaces"], manifest=True)
    conditions = data["conditions"]
    for key, value in object_map(conditions, "conditions"):
        domain(value, f"conditions.{key}", ("required",), ("hard",))
        for flag in ("required", "hard"):
            if flag in value and type(value[flag]) is not bool:
                raise ValueError(f"conditions.{key}.{flag} must be boolean")

    refs = []
    for part in array(data["parts"], "parts"):
        fields(part, "part", ("ref", "role", "manufacturer", "mpn", "package", "pin_map", "dnp"))
        refs.append(identifier(part["ref"]).casefold())
        for key in ("role", "manufacturer", "mpn", "package"):
            nonempty(part[key], f"part.{key}")
        if type(part["dnp"]) is not bool:
            raise ValueError("part.dnp must be boolean")
        pin_map = part["pin_map"]
        if not isinstance(pin_map, dict) or not pin_map:
            raise ValueError("part.pin_map must map pins to nets or NC")
        for pin, net in pin_map.items():
            nonempty(pin, "part pin")
            nonempty(net, "part pin assignment")
    unique(refs, "part references")

    files = data["files"]
    for key, entry in object_map(files, "files"):
        fields(entry, f"files.{key}", ("role", "relative_path", "sha256", "license"), ("materialize_as",))
        for name in entry:
            nonempty(entry[name], f"files.{key}.{name}")
        if entry["license"].strip().casefold() in UNKNOWN_LICENSES:
            raise ValueError(f"file {key} has an unknown license; cite it under provenance.sources")
        if not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
            raise ValueError(f"file {key} requires a lowercase SHA-256")
        if "materialize_as" in entry:
            name = entry["materialize_as"]
            if name in (".", "..") or any(char in name for char in "/\\:"):
                raise ValueError(f"file {key} materialize_as must be a basename")
    if not files and distribution != "reference-only":
        raise ValueError("a reusable module must declare at least one file")

    for slot, evidence in fields(data["evidence"], "evidence", SLOTS).items():
        fields(evidence, f"evidence.{slot}", ("status", "receipt"), ("conditions", "note"))
        status, receipt = evidence["status"], evidence["receipt"]
        if status == "pending":
            if receipt is not None:
                raise ValueError(f"pending evidence {slot} needs a null receipt")
        elif status in ("pass", "fail"):
            if identifier(receipt) not in files:
                raise ValueError(f"evidence {slot} requires a registered receipt")
        else:
            raise ValueError(f"invalid evidence status: {slot}")
        if "note" in evidence:
            nonempty(evidence["note"], f"evidence.{slot}.note")
        for key, bounds in object_map(evidence.get("conditions", {}), f"evidence.{slot}.conditions"):
            domain(bounds, f"evidence.{slot}.conditions.{key}")
            if key not in conditions or conditions[key].get("unit") != bounds.get("unit"):
                raise ValueError(f"evidence {slot} has an undeclared condition or different unit: {key}")

    allowances = {}
    for item in array(data.get("allowed_changes", []), "allowed_changes"):
        domain(item, "allowed change", ("parameter", "change_kind"))
        parameter = identifier(item["parameter"])
        if parameter in allowances:
            raise ValueError(f"duplicate allowed change parameter: {parameter}")
        allowances[parameter] = item["change_kind"]
        if item["change_kind"] not in CHANGE_KINDS:
            raise ValueError(f"unknown change kind: {parameter}")
        if parameter in conditions and conditions[parameter].get("unit") != item.get("unit"):
            raise ValueError(f"allowed change uses a different condition type or unit: {parameter}")

    ids = []
    for item in array(data.get("forbidden_combinations", []), "forbidden_combinations"):
        fields(item, "forbidden combination", ("id", "when", "reason"))
        ids.append(identifier(item["id"]))
        nonempty(item["reason"], "forbidden combination reason")
        predicates(item["when"], "forbidden combination when", conditions)
        if not item["when"]:
            raise ValueError("forbidden combination must have a condition")
    unique(ids, "forbidden combination ids")

    ids = []
    for item in array(data.get("layout_constraints", []), "layout_constraints"):
        fields(item, "layout constraint", ("id", "object", "criterion"), ("when", "evidence"))
        ids.append(identifier(item["id"]))
        for key in ("object", "criterion"):
            nonempty(item[key], f"layout constraint {key}")
        predicates(item.get("when", {}), "layout constraint when", conditions)
        string_refs(item.get("evidence", []), "layout constraint evidence", files)
    unique(ids, "layout constraint ids")

    parameters = []
    for item in array(data.get("change_impact", []), "change_impact"):
        fields(item, "change impact", ("parameter", "change_kind", "checks", "invalidates", "reason"))
        parameter = identifier(item["parameter"])
        parameters.append(parameter)
        if item["change_kind"] not in CHANGE_KINDS:
            raise ValueError(f"unknown impact change kind: {parameter}")
        if parameter in allowances and item["change_kind"] != allowances[parameter]:
            raise ValueError(f"allowed change and impact assign different kinds: {parameter}")
        string_refs(item["checks"], "impact checks")
        string_refs(item["invalidates"], "impact invalidated evidence", SLOTS)
        nonempty(item["reason"], "impact reason")
    unique(parameters, "impact parameters")


def module_root(library):
    root = library.expanduser().absolute()
    if linked_path(root):
        raise ValueError("linked module root is not accepted")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("module root must be a directory")
    return root


def load_module(root, manifest, expected_hash=None):
    if manifest.is_absolute():
        manifest = manifest.relative_to(root)
    if len(manifest.parts) != 3 or manifest.name != "module.json":
        raise ValueError("module manifest path must be <module_id>/<revision>/module.json")
    for segment in manifest.parts[:2]:
        identifier(segment)
    path = selected_file(root, manifest.as_posix())
    raw = path.read_bytes()
    manifest_hash = hashlib.sha256(raw).hexdigest()
    if expected_hash is not None and manifest_hash != expected_hash:
        raise ValueError("module manifest SHA-256 mismatch")
    data = read_json(raw)
    validate_manifest(data)
    relative = Path(data["module_id"], data["revision"], "module.json")
    if path.relative_to(root).as_posix() != relative.as_posix():
        raise ValueError("module manifest path must be <module_id>/<revision>/module.json")
    paths = {path}
    for key, entry in data["files"].items():
        name = entry["relative_path"]
        if any(char in name for char in "\\:") or any(segment in ("", ".", "..") for segment in name.split("/")):
            raise ValueError(f"file {key} requires a normalized relative path inside the module")
        source = selected_file(path.parent, name)
        if source in paths:
            raise ValueError(f"file {key} repeats a registered path or the manifest")
        paths.add(source)
        if file_hash(source) != entry["sha256"]:
            raise ValueError(f"file {key} SHA-256 mismatch")
    identity = {key: data[key] for key in ("module_id", "revision", "variant")}
    return data, {**identity, "manifest_sha256": manifest_hash}, relative.as_posix()


def validate_request(request):
    fields(request, "module request", optional=("conditions", "interfaces", "changes"))
    for key, value in object_map(request.get("conditions", {}), "requested conditions"):
        if isinstance(value, str) and value.strip():
            continue
        fields(value, f"requested condition {key}", ("value", "unit"))
        if not number(value["value"]):
            raise ValueError(f"requested condition {key} must have a finite numeric value")
        nonempty(value["unit"], f"requested condition {key} unit")
    validate_interfaces(request.get("interfaces", []), manifest=False)
    objects = []
    for item in array(request.get("changes", []), "changes"):
        fields(item, "change", ("object", "kind", "before", "after"))
        objects.append(identifier(item["object"]))
        if item["kind"] not in CHANGE_KINDS:
            raise ValueError(f"unknown requested change kind: {item['kind']}")
    unique(objects, "changed objects")
    return request


def match_domain(value, domain):
    """Return True, False or None (missing value, type, or unit)."""
    if "enum" in domain or "equals" in domain:
        if not isinstance(value, str):
            return None
        return value in domain["enum"] if "enum" in domain else value == domain["equals"]
    if not isinstance(value, dict) or value.get("unit") != domain["unit"] or not number(value.get("value")):
        return None
    return domain["min"] <= value["value"] <= domain["max"]


def match_predicates(values, rules):
    results = [match_domain(values.get(key), rule) for key, rule in rules.items()]
    if False in results:
        return False
    return None if None in results else True


def bounds_only(domain):
    return {key: domain[key] for key in ("unit", "min", "max", "enum") if key in domain}


def change_impact(data, request, deviations):
    declared = {item["parameter"]: item for item in data.get("change_impact", [])}
    allowed = {item["parameter"]: item for item in data.get("allowed_changes", [])}
    explicit = {item["object"]: item for item in request.get("changes", []) if item["before"] != item["after"]}
    changes, local_recheck, invalidated = [], [], set()
    for name in dict.fromkeys([*explicit, *deviations]):
        item = explicit.get(name)
        rule = declared.get(name)
        permission = allowed.get(name)
        after = item["after"] if item else request["conditions"][name]
        before = item["before"] if item else bounds_only(data["conditions"].get(name, {})) or None
        allowed_result = match_domain(after, permission) if permission is not None else None
        same_value = not (item and name in request.get("conditions", {}) and request["conditions"][name] != after)
        mapped = (
            same_value and "allowed_changes" in data and rule and rule["change_kind"] != "unknown"
            and (not item or item["kind"] == rule["change_kind"])
        )
        if mapped:
            kind, checks, slots, reason = (
                rule["change_kind"], rule["checks"], rule["invalidates"], rule["reason"]
            )
        else:
            kind, checks, slots = "unknown", ["change-impact"], SLOTS
            reason = "change has incomplete or inconsistent allowance and impact declarations"
            if not same_value:
                reason = "requested condition and explicit change disagree"
            if rule:
                checks = list(dict.fromkeys([*checks, *rule["checks"]]))
                reason = f"{reason}. {rule['reason']}"
        changes.append({"object": name, "kind": kind, "variant": data["variant"], "before": before, "after": after})
        local_recheck.append({"parameter": name, "checks": checks, "invalidates": list(slots), "reason": reason,
                              "allowance": "undeclared" if permission is None else
                              {True: "within", False: "outside", None: "unknown"}[allowed_result],
                              "mapping": "declared" if rule else "undeclared",
                              "basis": "explicit_change" if item else "declared_conditions"})
        invalidated.update(slots)
    return {"changes": changes, "local_recheck": local_recheck,
            "invalidated_evidence": [name for name in SLOTS if name in invalidated]}


def assess(data, identity, manifest, request):
    requested = dict(request.get("conditions", {}))
    for item in request.get("changes", []):
        name = item["object"]
        if name in data["conditions"] and item["before"] != item["after"]:
            requested[name] = item["after"]
    conditions = {}
    issues = []
    deviations = []
    for key, bounds in data["conditions"].items():
        result = match_domain(requested.get(key), bounds)
        if result is True:
            status = "within"
        elif result is False:
            status = "outside"
            deviations.append(key)
            issues.append({"status": "blocked" if bounds.get("hard") else "recheck", "field": key,
                           "reason": "outside declared condition"})
        elif key in requested or bounds["required"]:
            status = "unknown"
            issues.append({"status": "needs_input", "field": key, "reason": "value or matching unit required"})
        else:
            status = "not_supplied"
        conditions[key] = {"status": status, "actual": requested.get(key), "declared": bounds}
    for key in requested:
        if key in data["conditions"]:
            continue
        conditions[key] = {"status": "undeclared", "actual": requested[key]}
        issues.append({"status": "recheck", "field": key, "reason": "condition has no declared bounds"})
        deviations.append(key)

    ports = {row["id"]: row for row in data["interfaces"]}
    interfaces = []
    for requirement in request.get("interfaces", []):
        port = ports.get(requirement["id"], {})
        differences = [key for key, value in requirement.items() if port.get(key) != value]
        interfaces.append({"id": requirement["id"], "status": "mismatch" if differences else "match",
                           "differences": differences, "declared": port or None})
        if differences:
            issues.append({"status": "blocked", "field": requirement["id"], "reason": "requested interface mismatch"})

    distribution = data["provenance"]["distribution"]
    if distribution == "reference-only":
        issues.append({"status": "blocked", "field": "provenance", "reason": "reference-only distribution"})

    forbidden = []
    for item in data.get("forbidden_combinations", []):
        matched = match_predicates(requested, item["when"])
        forbidden.append({**item, "status": {True: "matched", False: "clear", None: "unknown"}[matched]})
        if matched is not False:
            issues.append({"status": "blocked" if matched else "needs_input", "field": item["id"],
                           "reason": item["reason"]})

    layout = [
        {**item, "applicability": {True: "applies", False: "does_not_apply", None: "unknown"}[
            match_predicates(requested, item.get("when", {}))]}
        for item in data.get("layout_constraints", [])
    ]
    recheck = change_impact(data, request, deviations)
    for row in recheck["local_recheck"]:
        if row["basis"] == "explicit_change":
            issues.append({"status": "recheck", "field": row["parameter"], "reason": row["reason"]})
    invalidated = set(recheck["invalidated_evidence"])
    evidence = {}
    for name, entry in data["evidence"].items():
        if name in invalidated:
            coverage = "recheck"
        elif entry["status"] == "pending":
            coverage = "pending"
        elif "conditions" not in entry:
            coverage = "undeclared"
        else:
            matched = match_predicates(requested, entry["conditions"])
            coverage = {True: "declared_in_scope", False: "out_of_scope", None: "unknown"}[matched]
        evidence[name] = {**entry, "coverage": coverage}
    recheck["reuse_candidates"] = [
        name for name in SLOTS if evidence[name]["status"] == "pass" and evidence[name]["coverage"] == "declared_in_scope"
    ]
    status = next((name for name in ("blocked", "needs_input", "recheck")
                   if any(issue["status"] == name for issue in issues)), "fits")
    return {
        "schema": "hardware-module-fit-v1", "status": status, "module": identity, "manifest": manifest,
        "integrity_ok": True, "provenance": data["provenance"], "conditions": conditions, "interfaces": interfaces,
        "declared_interfaces": data["interfaces"], "parts": data["parts"],
        "forbidden_combinations": {"status": "declared" if "forbidden_combinations" in data else "undeclared",
                                   "results": forbidden},
        "layout_constraints": {"status": "declared" if "layout_constraints" in data else "undeclared",
                               "results": layout},
        "evidence": evidence, "issues": issues, "impact": recheck,
        "engineering_validation": "not_performed_by_indexer",
    }


def module_fit(library, manifest, request, expected_hash=None):
    root = module_root(library)
    return assess(*load_module(root, manifest, expected_hash), validate_request(request))


def module_search(library, query, request, limit):
    root = module_root(library)
    terms = query.casefold().split()
    validate_request(request)
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    matches, invalid = [], []

    def subdirectories(parent):
        for path in sorted(parent.iterdir()):
            if linked_path(path):
                invalid.append({"manifest": path.relative_to(root).as_posix(), "error": "linked module path"})
            elif path.is_dir():
                yield path

    for module in subdirectories(root):
        for revision in subdirectories(module):
            manifest = revision / "module.json"
            if not linked_path(manifest) and not manifest.exists():
                continue
            try:
                data, identity, relative = load_module(root, manifest)
                ports = [port[key] for port in data["interfaces"]
                         for key in ("id", "role", "direction", "reference_domain")]
                haystack = "\n".join([data["module_id"], data["function"], *data["tags"], *ports]).casefold()
                if all(term in haystack for term in terms):
                    matches.append({
                        "module": identity, "manifest": relative, "function": data["function"],
                        "tags": data["tags"], "scope": data["scope"], "fit": assess(data, identity, relative, request),
                    })
            except (OSError, ValueError, TypeError) as exc:
                invalid.append({"manifest": manifest.relative_to(root).as_posix(), "error": str(exc)})

    def revision_order(match):
        return [(1, int(part)) if part.isdecimal() else (0, part.casefold())
                for part in re.findall(r"[0-9]+|[^0-9]+", match["module"]["revision"])]

    matches.sort(key=revision_order, reverse=True)
    matches.sort(key=lambda row: (FIT_ORDER[row["fit"]["status"]], -len(row["fit"]["impact"]["reuse_candidates"])))
    return {"schema": "hardware-module-search-v1", "query": query, "matches": matches[:limit],
            "total_matches": len(matches), "invalid_modules": invalid,
            "order": "fit status, declared applicable passing evidence count, natural revision descending"}
