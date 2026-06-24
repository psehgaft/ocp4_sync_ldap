#!/usr/bin/env python3
from __future__ import annotations
import argparse, collections, datetime as dt, html, json, os
from pathlib import Path
from typing import Any

GENERATOR_VERSION = "1.1.0"
RISK_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}
READ = {"get", "list", "watch"}
WRITE = {"create", "update", "patch", "delete", "deletecollection"}


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"items": []}


def as_items(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, dict) and isinstance(obj.get("items"), list):
        return [x for x in obj["items"] if isinstance(x, dict)]
    return [obj] if isinstance(obj, dict) and obj else []


def safe_dict(value: Any) -> dict[str, Any]:
    """Return a dictionary or an empty dictionary for null/unexpected values."""
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    """Return a list or an empty list for null/unexpected values."""
    return value if isinstance(value, list) else []


def name(obj: dict[str, Any]) -> str:
    return str(safe_dict(obj.get("metadata")).get("name") or "")


def ns(obj: dict[str, Any]) -> str:
    return str(safe_dict(obj.get("metadata")).get("namespace") or "")


def esc(v: Any) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def csv(values: Any) -> str:
    if values is None:
        return ""
    if isinstance(values, (str, int, float, bool)):
        return str(values)
    return ", ".join(
        str(x)
        for x in safe_list(values)
        if x is not None and str(x) != ""
    )


def rule_normalize(rule: Any) -> dict[str, list[str]]:
    rule_dict = safe_dict(rule)
    return {
        "apiGroups": [str(x) for x in safe_list(rule_dict.get("apiGroups"))],
        "resources": [str(x) for x in safe_list(rule_dict.get("resources"))],
        "resourceNames": [str(x) for x in safe_list(rule_dict.get("resourceNames"))],
        "verbs": [str(x) for x in safe_list(rule_dict.get("verbs"))],
        "nonResourceURLs": [str(x) for x in safe_list(rule_dict.get("nonResourceURLs"))],
    }


def risk(rule: dict[str, list[str]], role: str = "") -> tuple[str, str]:
    api, res, verbs = set(rule["apiGroups"]), set(rule["resources"]), set(rule["verbs"])
    level, reasons = "NONE", []
    def raise_to(candidate: str, reason: str) -> None:
        nonlocal level
        if RISK_ORDER[candidate] > RISK_ORDER[level]:
            level = candidate
        if reason not in reasons:
            reasons.append(reason)
    if role == "cluster-admin": raise_to("CRITICAL", "cluster-admin")
    if "*" in api and "*" in res and "*" in verbs: raise_to("CRITICAL", "complete wildcard")
    elif "*" in api or "*" in res or "*" in verbs: raise_to("HIGH", "partial wildcard")
    if verbs & {"bind", "escalate", "impersonate"}: raise_to("CRITICAL", "privilege escalation verb")
    if "serviceaccounts/token" in res and verbs & (WRITE | {"*"}): raise_to("CRITICAL", "service-account token creation")
    if "nodes/proxy" in res and verbs & ({"get", "create", "*"} | WRITE): raise_to("CRITICAL", "node proxy")
    if res & {"roles", "rolebindings", "clusterroles", "clusterrolebindings"} and verbs & (WRITE | {"bind", "escalate", "*"}):
        raise_to("CRITICAL", "RBAC mutation")
    if ("secrets" in res or "*" in res) and verbs & (READ | WRITE | {"*"}): raise_to("HIGH", "Secret access")
    if res & {"pods/exec", "pods/attach", "pods/portforward"} and verbs & {"get", "create", "*"}: raise_to("HIGH", "interactive pod access")
    if "securitycontextconstraints" in res and verbs & {"use", "*"}: raise_to("HIGH", "SCC use")
    if res & {"certificatesigningrequests/approval", "signers"} and verbs & {"approve", "sign", "update", "patch", "*"}: raise_to("HIGH", "certificate approval/signing")
    if level == "NONE" and verbs & WRITE: raise_to("MEDIUM", "resource mutation")
    if level == "NONE" and verbs and verbs.issubset(READ): raise_to("LOW", "read-only")
    return level, ", ".join(reasons)


def maxrisk(levels: list[str]) -> str:
    return max(levels, key=lambda x: RISK_ORDER[x], default="NONE")


def chart(title: str, values: dict[str, int] | collections.Counter, top: int = 20) -> str:
    pairs = sorted(values.items(), key=lambda x: (-x[1], x[0]))[:top]
    if not pairs:
        return f'<div class="chart"><h3>{esc(title)}</h3><p>No data.</p></div>'
    maxv = max(v for _, v in pairs) or 1
    rows = []
    for label, value in pairs:
        pct = max(1, round(value * 100 / maxv))
        rows.append(f'<div class="bar-row"><span title="{esc(label)}">{esc(label)}</span><div class="bar"><i style="width:{pct}%"></i></div><b>{value}</b></div>')
    return f'<div class="chart"><h3>{esc(title)}</h3>{"".join(rows)}</div>'


def table(section_id: str, title: str, columns: list[tuple[str, str]], rows: list[dict[str, Any]], description: str = "") -> str:
    heads = "".join(f"<th>{esc(label)}</th>" for _, label in columns)
    body = []
    for row in rows:
        search = " ".join(str(row.get(k, "")) for k, _ in columns).lower()
        cells = "".join(f"<td>{esc(row.get(k, ''))}</td>" for k, _ in columns)
        body.append(f'<tr data-search="{esc(search)}" data-risk="{esc(str(row.get("risk", "")).upper())}">{cells}</tr>')
    if not body:
        body.append(f'<tr><td colspan="{len(columns)}">No records available.</td></tr>')
    return f'''<section id="{esc(section_id)}" class="section"><h2>{esc(title)} <small>{len(rows)}</small></h2><p>{esc(description)}</p><input class="local-filter" data-table="{esc(section_id)}-table" placeholder="Filter this table"><div class="table-wrap"><table id="{esc(section_id)}-table"><thead><tr>{heads}</tr></thead><tbody>{''.join(body)}</tbody></table></div></section>'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    d = args.input_dir

    metadata = safe_dict(load(d / "metadata.json"))
    cvs, oauths, auths = as_items(load(d / "clusterversion.json")), as_items(load(d / "oauth.json")), as_items(load(d / "authentication.json"))
    identities, users, groups = as_items(load(d / "identities.json")), as_items(load(d / "users.json")), as_items(load(d / "groups.json"))
    sas, namespaces = as_items(load(d / "serviceaccounts.json")), as_items(load(d / "namespaces.json"))
    roles, rbs = as_items(load(d / "roles.json")), as_items(load(d / "rolebindings.json"))
    crs, crbs = as_items(load(d / "clusterroles.json")), as_items(load(d / "clusterrolebindings.json"))
    sccs = as_items(load(d / "sccs.json"))

    role_index = {
        (ns(x), name(x)): [rule_normalize(r) for r in safe_list(x.get("rules"))]
        for x in roles
    }
    cr_index = {
        name(x): [rule_normalize(r) for r in safe_list(x.get("rules"))]
        for x in crs
    }
    group_users, user_groups = {}, collections.defaultdict(list)
    for g in groups:
        group_users[name(g)] = [str(x) for x in safe_list(g.get("users"))]
        for u in group_users[name(g)]: user_groups[str(u)].append(name(g))

    identity_rows, idp_counts, identity_by_user = [], collections.Counter(), collections.defaultdict(list)
    for i in identities:
        iname = name(i); provider = str(i.get("providerName") or iname.split(":",1)[0] or "unknown"); u = str(safe_dict(i.get("user")).get("name") or "")
        idp_counts[provider] += 1
        if u: identity_by_user[u].append(iname)
        identity_rows.append({"identity": iname, "provider": provider, "provider_user": i.get("providerUserName", ""), "user": u})

    user_rows = []
    user_names = {name(u) for u in users}
    for u in users:
        uname = name(u)
        user_rows.append({"user": uname, "full_name": u.get("fullName", ""), "identities": csv(u.get("identities") or identity_by_user.get(uname)), "groups": csv(sorted(user_groups.get(uname, []))), "group_count": len(user_groups.get(uname, []))})
    group_rows = [{"group": name(g), "user_count": len(safe_list(g.get("users"))), "users": csv(g.get("users"))} for g in groups]

    oauth_rows = []
    for o in oauths:
        for p in safe_list(safe_dict(o.get("spec")).get("identityProviders")):
            p = safe_dict(p)
            oauth_rows.append({"name": p.get("name", ""), "type": p.get("type", ""), "mapping": p.get("mappingMethod", "")})

    assignments, bound_rules = [], []
    subject_counts, scope_counts, verb_counts, risk_counts = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    known_groups = set(group_users)
    external_groups = set()
    for scope, bindings in (("Cluster", crbs), ("Namespace", rbs)):
        for b in bindings:
            bns = "" if scope == "Cluster" else ns(b); bref = safe_dict(b.get("roleRef")); rkind, rname = str(bref.get("kind") or ""), str(bref.get("name") or "")
            rr = role_index.get((bns, rname), []) if rkind == "Role" else cr_index.get(rname, [])
            levels, reasons, verbs_u, resources_u, api_u = [], [], set(), set(), set()
            for idx, r in enumerate(rr, 1):
                lev, why = risk(r, rname); levels.append(lev); reasons.extend([x for x in why.split(", ") if x]); verbs_u.update(r["verbs"]); resources_u.update(r["resources"]); api_u.update(r["apiGroups"])
                verb_counts.update(r["verbs"])
                bound_rules.append({"scope": scope, "namespace": bns, "binding": name(b), "role_kind": rkind, "role": rname, "rule": idx, "api_groups": csv(r["apiGroups"]), "resources": csv(r["resources"]), "resource_names": csv(r["resourceNames"]), "verbs": csv(r["verbs"]), "non_resource_urls": csv(r["nonResourceURLs"]), "risk": lev, "reason": why})
            if not rr: levels, reasons = ["NONE"], ["Role not collected or has no rules"]
            br = maxrisk(levels)
            for s in safe_list(b.get("subjects")):
                s = safe_dict(s)
                sk, sn, sns = str(s.get("kind") or ""), str(s.get("name") or ""), str(s.get("namespace") or "")
                subject_counts[sk] += 1; scope_counts[scope] += 1; risk_counts[br] += 1
                if sk == "Group" and sn not in known_groups: external_groups.add(sn)
                assignments.append({"scope": scope, "namespace": bns, "binding": name(b), "role_kind": rkind, "role": rname, "subject_kind": sk, "subject_namespace": sns, "subject": sn, "api_groups": csv(sorted(api_u)), "resources": csv(sorted(resources_u)), "verbs": csv(sorted(verbs_u)), "risk": br, "reason": csv(sorted(set(reasons)))})

    by_user, by_group, by_sa = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
    for a in assignments:
        if a["subject_kind"] == "User": by_user[a["subject"]].append(a)
        elif a["subject_kind"] == "Group": by_group[a["subject"]].append(a)
        elif a["subject_kind"] == "ServiceAccount": by_sa[(a["subject_namespace"], a["subject"])].append(a)

    effective_users = []
    for uname in sorted(user_names | set(by_user)):
        found = False
        for a in by_user.get(uname, []):
            found = True; effective_users.append({"user": uname, "source": "Direct User binding", "group": "", "scope": a["scope"], "namespace": a["namespace"], "binding": a["binding"], "role": a["role"], "verbs": a["verbs"], "risk": a["risk"]})
        for g in user_groups.get(uname, []):
            for a in by_group.get(g, []):
                found = True; effective_users.append({"user": uname, "source": "OpenShift Group", "group": g, "scope": a["scope"], "namespace": a["namespace"], "binding": a["binding"], "role": a["role"], "verbs": a["verbs"], "risk": a["risk"]})
        if not found: effective_users.append({"user": uname, "source": "No collected binding", "group": "", "scope": "", "namespace": "", "binding": "", "role": "", "verbs": "", "risk": "NONE"})

    sa_rows, bound_sa = [], 0
    for sa in sas:
        key = (ns(sa), name(sa)); grants = by_sa.get(key, [])
        if grants:
            bound_sa += 1
            for a in grants: sa_rows.append({"namespace": key[0], "service_account": key[1], "scope": a["scope"], "binding_namespace": a["namespace"], "binding": a["binding"], "role": a["role"], "verbs": a["verbs"], "risk": a["risk"]})
        else: sa_rows.append({"namespace": key[0], "service_account": key[1], "scope": "Unbound", "binding_namespace": "", "binding": "", "role": "", "verbs": "", "risk": "NONE"})

    role_rows = []
    for r in roles:
        for idx, rule in enumerate(role_index[(ns(r), name(r))], 1):
            lev, why = risk(rule, name(r)); role_rows.append({"scope": "Namespace", "namespace": ns(r), "role": name(r), "rule": idx, "api_groups": csv(rule["apiGroups"]), "resources": csv(rule["resources"]), "resource_names": csv(rule["resourceNames"]), "verbs": csv(rule["verbs"]), "non_resource_urls": csv(rule["nonResourceURLs"]), "risk": lev, "reason": why})
    aggregation_rows = []
    for r in crs:
        for idx, rule in enumerate(cr_index[name(r)], 1):
            lev, why = risk(rule, name(r)); role_rows.append({"scope": "Cluster", "namespace": "", "role": name(r), "rule": idx, "api_groups": csv(rule["apiGroups"]), "resources": csv(rule["resources"]), "resource_names": csv(rule["resourceNames"]), "verbs": csv(rule["verbs"]), "non_resource_urls": csv(rule["nonResourceURLs"]), "risk": lev, "reason": why})
        if r.get("aggregationRule"): aggregation_rows.append({"cluster_role": name(r), "aggregation_rule": json.dumps(r["aggregationRule"], separators=(",", ":"))})

    scc_rows, scc_assign = [], []
    scc_names = {name(x) for x in sccs}
    for s in sccs:
        sname = name(s); direct_users = [str(x) for x in safe_list(s.get("users"))]; direct_groups = [str(x) for x in safe_list(s.get("groups"))]
        scc_rows.append({"scc": sname, "priority": s.get("priority", ""), "privileged": s.get("allowPrivilegedContainer", False), "host_network": s.get("allowHostNetwork", False), "host_pid": s.get("allowHostPID", False), "host_ipc": s.get("allowHostIPC", False), "host_ports": s.get("allowHostPorts", False), "read_only_rootfs": s.get("readOnlyRootFilesystem", False), "run_as_user": safe_dict(s.get("runAsUser")).get("type", ""), "selinux": safe_dict(s.get("seLinuxContext")).get("type", ""), "volumes": csv(s.get("volumes")), "allowed_capabilities": csv(s.get("allowedCapabilities")), "drop_capabilities": csv(s.get("requiredDropCapabilities")), "direct_users": csv(direct_users), "direct_groups": csv(direct_groups)})
        for x in direct_users: scc_assign.append({"scc": sname, "source": "Direct SCC user", "scope": "Cluster", "namespace": "", "subject_kind": "User/ServiceAccount", "subject": x, "binding": "", "role": ""})
        for x in direct_groups: scc_assign.append({"scc": sname, "source": "Direct SCC group", "scope": "Cluster", "namespace": "", "subject_kind": "Group", "subject": x, "binding": "", "role": ""})
    for a in assignments:
        rr = role_index.get((a["namespace"], a["role"]), []) if a["role_kind"] == "Role" else cr_index.get(a["role"], [])
        for r in rr:
            if ("securitycontextconstraints" in r["resources"] or "*" in r["resources"]) and ("use" in r["verbs"] or "*" in r["verbs"]):
                for target in (r["resourceNames"] or sorted(scc_names)):
                    subject = f'{a["subject_namespace"]}/{a["subject"]}' if a["subject_kind"] == "ServiceAccount" else a["subject"]
                    scc_assign.append({"scc": target, "source": "RBAC use verb", "scope": a["scope"], "namespace": a["namespace"], "subject_kind": a["subject_kind"], "subject": subject, "binding": a["binding"], "role": a["role"]})

    warnings = []
    for role_obj in roles:
        if "rules" in role_obj and role_obj.get("rules") is None:
            warnings.append({
                "category": "Data normalization",
                "item": f"Role/{ns(role_obj)}/{name(role_obj)}",
                "message": "The API returned rules: null; the report treated it as an empty rule list."
            })
    for role_obj in crs:
        if "rules" in role_obj and role_obj.get("rules") is None:
            warnings.append({
                "category": "Data normalization",
                "item": f"ClusterRole/{name(role_obj)}",
                "message": "The API returned rules: null; the report treated it as an empty rule list."
            })
    for p in sorted(d.glob("*.error")):
        text = p.read_text(encoding="utf-8", errors="replace").strip()
        if text: warnings.append({"category": "Collection", "item": p.name, "message": text})
    for g in sorted(external_groups): warnings.append({"category": "External/unsynchronized group", "item": g, "message": "Referenced by RBAC, but no matching OpenShift Group object was collected; user membership cannot be expanded."})

    cv = cvs[0] if cvs else {}; version = str(safe_dict(safe_dict(cv.get("status")).get("desired")).get("version") or ""); cluster_id = str(safe_dict(cv.get("spec")).get("clusterID") or "")
    auth_type = str(safe_dict(auths[0].get("spec") if auths else {}).get("type") or "")
    cards = [("Users",len(users)),("Identities",len(identities)),("Groups",len(groups)),("ServiceAccounts",len(sas)),("Roles",len(roles)),("ClusterRoles",len(crs)),("RoleBindings",len(rbs)),("ClusterRoleBindings",len(crbs)),("SCCs",len(sccs)),("Namespaces",len(namespaces))]
    charts = [chart("Identities by provider", idp_counts), chart("Users per group", {x["group"]:x["user_count"] for x in group_rows}), chart("RBAC subjects", subject_counts), chart("Cluster vs namespace scope", scope_counts), chart("Assignment risk", risk_counts), chart("Verb frequency", verb_counts), chart("ServiceAccount binding state", {"Bound":bound_sa,"Unbound":max(0,len(sas)-bound_sa)}), chart("SCC assignment records", collections.Counter(x["scc"] for x in scc_assign))]

    sections = [
      table("idps","Configured identity providers",[("name","Name"),("type","Type"),("mapping","Mapping method")],oauth_rows,"OAuth/cluster identity providers; Secret values are not collected."),
      table("identities","Identities",[("identity","Identity"),("provider","Provider"),("provider_user","Provider user"),("user","OpenShift user")],identity_rows,"Identity-to-user mapping."),
      table("users","Users",[("user","User"),("full_name","Full name"),("identities","Identities"),("groups","Groups"),("group_count","Group count")],user_rows,"OpenShift users and group membership."),
      table("groups","Groups",[("group","Group"),("user_count","Users"),("users","Members")],group_rows,"Only membership represented in OpenShift Group objects can be expanded."),
      table("assignments","RBAC assignments",[("scope","Scope"),("namespace","Namespace"),("binding","Binding"),("role_kind","Role kind"),("role","Role"),("subject_kind","Subject kind"),("subject_namespace","Subject namespace"),("subject","Subject"),("verbs","Verbs"),("resources","Resources"),("risk","Risk"),("reason","Reason")],assignments,"Bindings expanded by subject and resolved role rules."),
      table("effective-users","User access relationships",[("user","User"),("source","Source"),("group","Group"),("scope","Scope"),("namespace","Namespace"),("binding","Binding"),("role","Role"),("verbs","Verbs"),("risk","Risk")],effective_users,"Direct and group-inherited access."),
      table("serviceaccounts","ServiceAccounts",[("namespace","SA namespace"),("service_account","ServiceAccount"),("scope","Scope"),("binding_namespace","Binding namespace"),("binding","Binding"),("role","Role"),("verbs","Verbs"),("risk","Risk")],sa_rows,"All ServiceAccounts, including unbound accounts."),
      table("roles","Role rules",[("scope","Scope"),("namespace","Namespace"),("role","Role"),("rule","Rule"),("api_groups","API groups"),("resources","Resources"),("resource_names","Resource names"),("verbs","Verbs"),("non_resource_urls","Non-resource URLs"),("risk","Risk"),("reason","Reason")],role_rows,"Complete Role and ClusterRole PolicyRules."),
      table("bound-rules","Rules used by bindings",[("scope","Scope"),("namespace","Namespace"),("binding","Binding"),("role_kind","Role kind"),("role","Role"),("rule","Rule"),("api_groups","API groups"),("resources","Resources"),("resource_names","Resource names"),("verbs","Verbs"),("risk","Risk"),("reason","Reason")],bound_rules,"Rules resolved from each binding roleRef."),
      table("sccs","SCC characteristics",[("scc","SCC"),("priority","Priority"),("privileged","Privileged"),("host_network","Host network"),("host_pid","Host PID"),("host_ipc","Host IPC"),("host_ports","Host ports"),("read_only_rootfs","Read-only root FS"),("run_as_user","RunAsUser"),("selinux","SELinux"),("volumes","Volumes"),("allowed_capabilities","Allowed capabilities"),("drop_capabilities","Required dropped capabilities"),("direct_users","Direct users"),("direct_groups","Direct groups")],scc_rows,"Security characteristics and direct assignments."),
      table("scc-assignments","SCC relationships",[("scc","SCC"),("source","Source"),("scope","Scope"),("namespace","Namespace"),("subject_kind","Subject kind"),("subject","Subject"),("binding","Binding"),("role","Role")],scc_assign,"Direct SCC users/groups plus RBAC use grants."),
      table("aggregation","Aggregated ClusterRoles",[("cluster_role","ClusterRole"),("aggregation_rule","Aggregation rule")],aggregation_rows,"Rules can change through aggregation labels."),
      table("warnings","Warnings",[("category","Category"),("item","Item"),("message","Message")],warnings,"Collection errors and unresolved external group membership."),
    ]

    cards_html = ''.join(f'<div class="metric"><span>{esc(k)}</span><b>{v}</b></div>' for k,v in cards)
    generated = metadata.get("collectedAt") or dt.datetime.now(dt.timezone.utc).isoformat()
    doc = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OpenShift RBAC Report</title><style>
:root{{--bg:#f4f6f8;--panel:#fff;--border:#d2d2d2;--text:#151515;--muted:#5f6a72;--accent:#06c;--bar:#4f7cac}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}header{{background:#151515;color:#fff;padding:24px 32px}}header h1{{margin:0 0 8px}}header p{{margin:3px 0;color:#ddd}}nav{{position:sticky;top:0;z-index:9;background:#fff;border-bottom:1px solid var(--border);padding:10px 22px;white-space:nowrap;overflow:auto}}nav a{{margin-right:16px;color:var(--accent);text-decoration:none}}main{{max-width:1900px;margin:auto;padding:24px}}.notice{{background:#fff4cc;border-left:5px solid #f0ab00;padding:14px}}.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:12px;margin:18px 0}}.metric,.chart,.section{{background:var(--panel);border:1px solid var(--border);border-radius:6px;padding:15px}}.metric span{{color:var(--muted);display:block}}.metric b{{font-size:26px}}.charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:14px}}.chart h3{{margin-top:0}}.bar-row{{display:grid;grid-template-columns:190px 1fr 55px;gap:8px;align-items:center;margin:7px 0}}.bar-row span{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.bar{{height:17px;background:#edf0f2;border-radius:3px}}.bar i{{display:block;height:100%;background:var(--bar);border-radius:3px}}.section{{margin:20px 0}}.section h2{{margin:0}}.section h2 small{{background:#e7f1fa;color:#046;padding:2px 8px;border-radius:12px}}.global,.local-filter,select,button{{padding:8px 10px;border:1px solid #8a8d90;border-radius:4px}}.controls{{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}}.local-filter{{margin:8px 0;width:320px}}.table-wrap{{overflow:auto;max-height:720px;border:1px solid var(--border)}}table{{border-collapse:collapse;width:100%;font-size:12px}}th{{position:sticky;top:0;background:#eee;z-index:1}}th,td{{padding:7px 8px;border-bottom:1px solid var(--border);border-right:1px solid #eee;text-align:left;vertical-align:top;white-space:pre-wrap}}tbody tr:hover{{background:#f5faff}}tr[data-risk="CRITICAL"] td:first-child{{border-left:5px solid #b1380b}}tr[data-risk="HIGH"] td:first-child{{border-left:5px solid #f0ab00}}tr[data-risk="MEDIUM"] td:first-child{{border-left:5px solid #8a8d90}}tr[data-risk="LOW"] td:first-child{{border-left:5px solid #3e8635}}footer{{color:var(--muted);padding:20px}}@media print{{nav,.controls,.local-filter{{display:none}}.table-wrap{{max-height:none;overflow:visible}}body{{background:#fff}}}}
</style></head><body><header><h1>OpenShift RBAC, Identity, ServiceAccount and SCC Report</h1><p>Version: {esc(version)} | Cluster ID: {esc(cluster_id)}</p><p>API: {esc(metadata.get('apiServer',''))} | Collector: {esc(metadata.get('collector',''))} | Collected: {esc(generated)}</p><p>Authentication: {esc(auth_type)}</p></header><nav><a href="#overview">Overview</a><a href="#identities">Identities</a><a href="#users">Users</a><a href="#assignments">Assignments</a><a href="#serviceaccounts">ServiceAccounts</a><a href="#roles">Roles</a><a href="#sccs">SCCs</a><a href="#warnings">Warnings</a></nav><main><section id="overview"><div class="notice">Read-only configuration report. Secret values are not collected. External IdP group membership can only be expanded when synchronized into OpenShift Group objects. Validate effective authorization with <code>oc auth can-i</code> and <code>oc adm policy who-can</code>.</div><div class="controls"><input id="global" class="global" placeholder="Global filter"><select id="risk"><option value="">All risks</option><option>CRITICAL</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option><option>NONE</option></select><button onclick="window.print()">Print / Save PDF</button></div><div class="metrics">{cards_html}</div><div class="charts">{''.join(charts)}</div></section>{''.join(sections)}<footer>Store this report and the evidence directory as sensitive security information.</footer></main><script>
function filterRows(){{let g=document.getElementById('global').value.toLowerCase(),r=document.getElementById('risk').value;document.querySelectorAll('tbody tr[data-search]').forEach(row=>{{let t=row.closest('table'),i=document.querySelector('.local-filter[data-table="'+t.id+'"]'),l=i?i.value.toLowerCase():'';row.style.display=((!g||row.dataset.search.includes(g))&&(!l||row.dataset.search.includes(l))&&(!r||row.dataset.risk===r))?'':'none'}})}}document.getElementById('global').addEventListener('input',filterRows);document.getElementById('risk').addEventListener('change',filterRows);document.querySelectorAll('.local-filter').forEach(i=>i.addEventListener('input',filterRows));
</script></body></html>'''
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(doc, encoding="utf-8"); os.chmod(args.output, 0o600)
    print(f"Generated: {args.output}")
    print(f"Generator version: {GENERATOR_VERSION}")
    print(json.dumps({"users":len(users),"identities":len(identities),"groups":len(groups),"serviceAccounts":len(sas),"assignments":len(assignments),"roles":len(roles)+len(crs),"sccs":len(sccs),"warnings":len(warnings)}, sort_keys=True))
    return 0

if __name__ == "__main__": raise SystemExit(main())
