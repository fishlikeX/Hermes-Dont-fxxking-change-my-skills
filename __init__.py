"""别改我的技能！ — Dont fxxking change my skills!

Restores the skill-ownership guard that upstream commit e3d2e57c9
(NousResearch/hermes-agent, "background review can improve every skill") removed
from the content-write path. The background self-improvement fork may patch /
extend / prune only skills Hermes herself created, unless the user flips a
per-skill `allow`. Foreground (user-directed) content writes pass; deletion via
skill_manage is refused for every origin (the strictest tier).

Verdict table (tier per skill, stored in guard.json):

    action          auto(default)              allow      deny
    --------------  -------------------------  ---------  ---------
    patch/…(bg)     pass iff agent-created     pass       block
    patch/…(fg)     pass                       pass       pass
    delete (any)    block                      block      block

"agent-created" = ``_is_curator_managed_record``: ``created_by == "agent"`` or
``agent_created is True`` in skills/.usage.json. The flag is a curator opt-in,
not authorship proof, so a MISSING record is conservatively user-owned — better
to skip a useful lesson than to dilute a hand-written skill.

Fail-safe stance: upstream swallows hook exceptions ("failures never block"),
so we never raise. An internal error while classifying a background write is
treated as user-owned (fail-closed toward blocking) and logged; foreground is
never blocked by our own breakage.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).resolve().parent
PLUGIN_NAME = "dont-change-my-skills"
GUARD_FILE = PLUGIN_DIR / "guard.json"
AUDIT_FILE = PLUGIN_DIR / "audit.log"
_AUDIT_MAX_BYTES = 2_000_000

_CONTENT_ACTIONS = {"patch", "write_file", "remove_file"}
_KNOWN_TIERS = {"allow", "deny"}


# ---------------------------------------------------------------- guard file

def _load_guard() -> dict[str, str]:
    try:
        raw = json.loads(GUARD_FILE.read_text(encoding="utf-8-sig"))
        skills = raw.get("skills") if isinstance(raw, dict) else None
        if isinstance(skills, dict):
            return {str(k): v for k, v in skills.items() if v in _KNOWN_TIERS}
    except FileNotFoundError:
        return {}
    except Exception as exc:  # corrupt file => behave as empty, tell loudly
        logger.warning("skill-guard: guard.json unreadable (%s); treating as empty", exc)
    return {}


def _save_guard(skills: dict[str, str]) -> None:
    tmp = GUARD_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"skills": skills}, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, GUARD_FILE)


def set_tier(name: str, tier: Optional[str]) -> str:
    """tier: 'allow' | 'deny' | None (=auto, entry removed). Returns the new state."""
    skills = _load_guard()
    if tier is None:
        skills.pop(name, None)
    elif tier in _KNOWN_TIERS:
        skills[name] = tier
    else:
        raise ValueError(f"unknown tier {tier!r}")
    _save_guard(skills)
    return tier or "auto"


# ------------------------------------------------------------------- audit

def _audit(line: str) -> None:
    try:
        if AUDIT_FILE.exists() and AUDIT_FILE.stat().st_size > _AUDIT_MAX_BYTES:
            AUDIT_FILE.unlink()
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with AUDIT_FILE.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp} {line}\n")
    except Exception:
        logger.debug("skill-guard: audit write failed", exc_info=True)


# --------------------------------------------------------------- classify

def _classify(skill_name: str) -> str:
    """'agent' | 'bundled' | 'hub' | 'external' | 'user'. Never raises.

    Conservative by construction: anything we cannot positively prove Hermes
    created is user-owned. `pinned` is surfaced separately for the list UI but
    already implies protected semantics -> treated as user here (upstream
    pre-e3d2e57c9 behavior).
    """
    from tools import skill_usage

    try:
        if skill_usage.is_bundled(skill_name):
            return "bundled"
        if skill_usage.is_hub_installed(skill_name):
            return "hub"
    except Exception:
        pass

    try:
        from agent.skill_utils import is_external_skill_path
        skill_dir = skill_usage._find_skill_dir(skill_name)
        if skill_dir is not None and is_external_skill_path(skill_dir):
            return "external"
    except Exception:
        pass

    try:
        if skill_usage._is_curator_managed_record(skill_usage.get_record(skill_name)):
            return "agent"
    except Exception:
        # Cannot prove agent authorship; do NOT let the fork write.
        return "user"
    return "user"


# ------------------------------------------------------------------ verdict

def _decide(skill_name: str, action: str, origin: str) -> tuple[bool, str, str]:
    """(allow, tier, reason). tier is 'auto'|'allow'|'deny'; reason is audit text.

    Foreground: content writes pass (delete never does, decided by caller).
    Background: guard.json tier wins; auto defers to classify().
    """
    tier = _load_guard().get(skill_name, "auto")
    is_bg = origin == _background_sentinel()

    if not is_bg:
        return True, tier, "foreground (user-directed)"

    if tier == "deny":
        return False, tier, "user denied this skill (guard list)"
    if tier == "allow":
        return True, tier, "user allowed background edits"

    cls = _classify(skill_name)
    if cls == "agent":
        return True, tier, "agent-created, auto mode"
    return False, tier, f"user-owned ({cls}), guard active"


def _background_sentinel() -> str:
    from tools.skill_provenance import BACKGROUND_REVIEW
    return BACKGROUND_REVIEW


_BLOCK_TEMPLATE = (
    "skill-guard: '{name}' is {why}. The user's skill-ownership guard "
    "(`别改我的技能！` plugin) refuses background self-improvement writes to it. "
    "Do not retry this skill; if the lesson genuinely belongs elsewhere, patch an "
    "agent-created skill instead, or say 'Nothing to save.'"
)


# -------------------------------------------------------------------- hook

def _on_pre_tool_call(tool_name: str = "", args: Optional[dict[str, Any]] = None, **_kw: Any):
    """Veto background writes to user-owned skills. Never raises, never blocks
    the foreground, fail-closes the background path when classification breaks."""
    if tool_name != "skill_manage" or not isinstance(args, dict):
        return None
    action = args.get("action")
    name = str(args.get("name") or "").strip()
    if not name:
        return None

    try:
        origin = _origin()
        is_bg = origin == _background_sentinel()

        # ---- delete: strictest tier, every origin ----
        if action == "delete":
            if is_bg:
                _audit(f"BLOCK bg delete skill={name}")
                return {"action": "block", "message": (
                    f"skill-guard: background deletion of skill '{name}' is forbidden by the "
                    "user's `别改我的技能！` plugin. Never archive/delete skills here."
                )}
            _audit(f"BLOCK fg delete skill={name}")
            return {"action": "block", "message": (
                f"skill-guard: skill_manage(delete) on '{name}' is disabled by the "
                "`别改我的技能！` plugin (delete = most restricted tier). If the user truly "
                "wants it gone, they remove the folder via terminal or `hermes skills uninstall`."
            )}

        if action not in _CONTENT_ACTIONS:
            return None  # create/list/view etc.

        allow, tier, reason = _decide(name, action, origin)
        if allow:
            if is_bg:
                _audit(f"PASS bg {action} skill={name} tier={tier} ({reason})")
            return None

        why = reason.split("(", 1)[0].strip().rstrip(",")
        _audit(f"BLOCK bg {action} skill={name} tier={tier} ({reason})")
        return {"action": "block", "message": _BLOCK_TEMPLATE.format(name=name, why=why)}
    except Exception as exc:
        _audit(f"ERROR skill_manage action={action} skill={name} origin={_safe_origin()} err={exc!r}")
        if _safe_origin() == _sentinel_or_fallback():
            # Background + broken internals: fail CLOSED toward protection.
            return {"action": "block", "message": (
                f"skill-guard: cannot verify ownership of '{name}' ({exc!r}); refusing the "
                "background write to stay safe."
            )}
        return None  # foreground never blocked by our own breakage


def _origin() -> str:
    from tools.skill_provenance import get_current_write_origin
    return get_current_write_origin()


def _safe_origin() -> str:
    try:
        return _origin()
    except Exception:
        return "unknown"


def _sentinel_or_fallback() -> str:
    try:
        return _background_sentinel()
    except Exception:
        return "background_review"  # upstream literal; matches nothing else


# ------------------------------------------------------------------- list

def list_skills() -> list[dict[str, Any]]:
    """Every skill under the skills root, classified, with its guard tier."""
    from tools import skill_usage
    from agent.skill_utils import iter_skill_index_files

    guards = _load_guard()
    usage = {}
    try:
        usage = skill_usage.load_usage()
    except Exception:
        pass
    rows: list[dict[str, Any]] = []
    root = skill_usage._skills_dir()
    for md_path in iter_skill_index_files(root, "SKILL.md"):
        path = Path(md_path)
        dir_name = path.parent.name
        name = _read_name(path) or dir_name
        cls = _classify(name)
        rec = usage.get(name) or usage.get(dir_name) or {}
        rows.append({
            "name": name,
            "class": cls,
            "tier": guards.get(name, "auto"),
            "pinned": bool(rec.get("pinned")),
            "archived": rec.get("state") == "archived",
        })
    # guard entries whose skill vanished from the tree (renamed/removed) — keep them visible
    seen = {r["name"] for r in rows}
    for orphan in sorted(set(guards) - seen):
        rows.append({"name": orphan, "class": "gone", "tier": guards[orphan],
                     "pinned": False, "archived": False})
    rows.sort(key=lambda r: r["name"].lower())
    return rows


def _read_name(skill_md: Path) -> str:
    try:
        for line in skill_md.read_text(encoding="utf-8-sig", errors="replace")[:4000].splitlines():
            line = line.strip()
            if line.startswith("name:"):
                return line.split(":", 1)[1].strip().strip("\"'")
    except Exception:
        pass
    return ""


# -------------------------------------------------------------------- CLI

def _cmd_list(_args) -> None:
    rows = list_skills()
    by_tier = {"allow": 0, "deny": 0, "auto": 0}
    for r in rows:
        by_tier[r["tier"]] += 1
        mark = {"agent": "AGENT ", "user": "USER  ", "bundled": "BUNDL ",
                "hub": "HUB   ", "external": "EXT   ", "gone": "GONE  "}.get(r["class"], "?")
        extra = "".join([" *PIN" if r["pinned"] else "", " *ARCHIVED" if r["archived"] else ""])
        tier = "" if r["tier"] == "auto" else f"  [{r['tier'].upper()}]"
        print(f"{mark} {r['name']}{extra}{tier}")
    print(f"\n{len(rows)} skills — auto:{by_tier['auto']} allow:{by_tier['allow']} deny:{by_tier['deny']}")
    print("auto = guard rule: background review may modify AGENT-created skills only")


def _setup_parser(sub):
    sub.description = "Ownership guard for the background self-improvement fork"
    sp = sub.add_subparsers(dest="cmd", required=True)
    sp.add_parser("list", help="list every skill with class and guard tier")
    for verb in ("allow", "deny"):
        p = sp.add_parser(verb, help=f"let background review {verb} this specific skill" if verb == "allow"
                          else "forbid even agent-created skill from auto-improvement")
        p.add_argument("name")
    p = sp.add_parser("reset", help="return a skill to auto")
    p.add_argument("name")
    sp.add_parser("status", help="guard + audit summary")


def _handle(args) -> None:
    if args.cmd == "list":
        _cmd_list(args)
    elif args.cmd in ("allow", "deny"):
        print(f"'{args.name}' -> {set_tier(args.name, args.cmd)}")
    elif args.cmd == "reset":
        print(f"'{args.name}' -> {set_tier(args.name, None)}")
    elif args.cmd == "status":
        g = _load_guard()
        n_block = 0
        if AUDIT_FILE.exists():
            n_block = sum(1 for _ in AUDIT_FILE.open(encoding="utf-8", errors="replace") if " BLOCK " in _ or "BLOCK" in _)
        print(f"guard file : {GUARD_FILE} ({len(g)} explicit entries)")
        print(f"audit log  : {AUDIT_FILE} ({n_block} blocked so far)")
        print(f"last lines :")
        if AUDIT_FILE.exists():
            lines = AUDIT_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-5:]
            for ln in lines:
                print("  " + ln)


# ---------------------------------------------------------------- register

def register(ctx) -> None:
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    ctx.register_cli_command(
        name="skill-guard",
        help="别改我的技能！ — ownership guard for agent-created skills",
        description="List skills, allow/deny background self-improvement per skill.",
        setup_fn=_setup_parser,
        handler_fn=_handle,
    )
    # NB: never reach for ctx.manifest here — `hermes plugins validate` calls
    # register() against a minimal recording stub, and the probe is a CI gate.
    logger.info("skill-guard: ownership guard active (plugin %s)", PLUGIN_NAME)
