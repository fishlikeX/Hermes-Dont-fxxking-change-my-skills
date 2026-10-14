"""Dashboard REST surface for `别改我的技能！` — mounted at /api/plugins/dont-change-my-skills/.

Thin layer over the plugin core (__init__.py next to the parent dir). The core
owns every verdict; this module only lists and edits the guard list, so the UI
can never disagree with the hook.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_PKG = "dont_change_my_skills_core"


def _core():
    """Import the plugin core from the parent dir once, under a private name."""
    if _PKG in sys.modules:
        return sys.modules[_PKG]
    init_py = Path(__file__).resolve().parent.parent / "__init__.py"
    spec = importlib.util.spec_from_file_location(_PKG, init_py)
    if spec is None or spec.loader is None:
        raise HTTPException(500, "skill-guard core not found next to plugin_api.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_PKG] = mod
    spec.loader.exec_module(mod)
    return mod


class TierIn(BaseModel):
    skill: str
    tier: str  # allow | deny | auto


@router.get("/skills")
def skills() -> list[dict[str, Any]]:
    return _core().list_skills()


@router.post("/tier")
def set_tier(body: TierIn) -> dict[str, str]:
    skill = body.skill.strip()
    if not skill:
        raise HTTPException(400, "skill name required")
    if body.tier not in {"allow", "deny", "auto"}:
        raise HTTPException(400, "tier must be allow|deny|auto")
    try:
        new = _core().set_tier(skill, None if body.tier == "auto" else body.tier)
    except ValueError:
        raise HTTPException(400, "bad tier")
    return {"skill": skill, "tier": new}


@router.get("/audit")
def audit(lines: int = 50) -> dict[str, Any]:
    core = _core()
    path = core.AUDIT_FILE
    n_total = 0
    tail: list[str] = []
    if path.exists():
        all_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        n_total = sum(1 for ln in all_lines if "BLOCK" in ln)
        tail = all_lines[-max(1, min(lines, 200)):]
    return {"blocked_total": n_total, "tail": tail}
