"""skill-guard 验收测试 — 直接打 pre_tool_call 钩子,真实 skills 树 + 真实 usage。

跑法(项目 python, hermes-agent 在 sys.path):
  python test_guard.py
验收对应用户五条规格中的拦截语义。
"""
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# hermes-agent checkout on sys.path; override with HERMES_AGENT for other machines
AGENT = os.environ.get("HERMES_AGENT", str(Path.home() / "AppData/Local/hermes/hermes-agent"))
sys.path.insert(0, AGENT)

SPEC = importlib.util.spec_from_file_location("guard", HERE / "__init__.py")
g = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(g)

from tools import skill_usage
from tools.skill_provenance import BACKGROUND_REVIEW

usage = skill_usage.load_usage()
agent_skills = sorted(n for n, r in usage.items()
                      if skill_usage._is_curator_managed_record(r) and r.get("state") != "archived")
user_skills = sorted(n for n, r in usage.items()
                     if not skill_usage._is_curator_managed_record(r) and r.get("state") != "archived")
if not agent_skills or not user_skills:
    raise SystemExit("need both agent-created and user-owned skills installed to run this test")

fails = []
def check(cond, label):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond: fails.append(label)

BG = {"_current_write_origin": BACKGROUND_REVIEW}

def hook(name, action, origin):
    from tools import skill_provenance
    tok = skill_provenance.set_current_write_origin(origin)
    try:
        return g._on_pre_tool_call(tool_name="skill_manage",
                                   args={"action": action, "name": name})
    finally:
        skill_provenance.reset_current_write_origin(tok)

print("样本: agent=%s... user=%s..." % (agent_skills[:2], user_skills[:2]))

# ── 1. 默认态: 后台改 agent 自产 → 放行
r = hook(agent_skills[0], "patch", BACKGROUND_REVIEW)
check(r is None, f"bg patch agent-created ({agent_skills[0]}) passes")

# ── 2. 默认态: 后台改用户 skill → 拦（样本从当前安装动态取样，测试不落任何真实 skill 名）
rows0 = {row["name"]: row for row in g.list_skills()}
user_sample = next(n for n in rows0 if rows0[n]["class"] in ("user", "hub", "external"))
agent_sample = next(n for n in rows0 if rows0[n]["class"] == "agent")
r = hook(user_sample, "patch", BACKGROUND_REVIEW)
check(r and r.get("action") == "block", f"bg patch user-owned ({user_sample}) blocked")
r = hook(agent_sample, "write_file", BACKGROUND_REVIEW)
check(r is None, f"bg write_file agent-created ({agent_sample}) passes")

# ── 3. allow 开关: 用户 skill 放开
g.set_tier(user_sample, "allow")
r = hook(user_sample, "patch", BACKGROUND_REVIEW)
check(r is None, "allowed user skill passes in bg")

# ── 4. deny 开关: agent 自产也禁
g.set_tier(agent_skills[0], "deny")
r = hook(agent_skills[0], "patch", BACKGROUND_REVIEW)
check(r and r.get("action") == "block", "denied agent skill blocked in bg")
g.set_tier(agent_skills[0], None)  # reset

# ── 5. delete 全档拦截(含前台、含 allow 名单内)
r = hook(user_sample, "delete", "assistant_tool")
check(r and r.get("action") == "block", "fg delete blocked even for allow-listed skill")
g.set_tier(user_sample, None)
r = hook(agent_skills[0], "delete", BACKGROUND_REVIEW)
check(r and r.get("action") == "block", "bg delete of agent skill blocked")
r = hook(agent_skills[0], "delete", "assistant_tool")
check(r and r.get("action") == "block", "fg delete of agent skill blocked")

# ── 6. 前台内容写直通(用户 skill)
r = hook(user_sample, "patch", "assistant_tool")
check(r is None, "fg patch user skill passes (user-directed)")

# ── 7. fail-safe: usage 查询爆炸时,后台写按用户对待,前台不炸
import tools.skill_usage as su
_orig = su.get_record
su.get_record = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
_origbundled, su.is_bundled = su.is_bundled, (lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
try:
    r = hook(agent_skills[0], "patch", BACKGROUND_REVIEW)
    check(r and r.get("action") == "block", "bg write fail-closed when classification explodes")
    r = hook(agent_skills[0], "patch", "assistant_tool")
    check(r is None, "fg write never blocked by our own breakage")
finally:
    su.get_record = _orig
    su.is_bundled = _origbundled

# ── 8. 无关工具直接放过
check(g._on_pre_tool_call(tool_name="write_file", args={"path": "x"}) is None, "other tools untouched")
check(g._on_pre_tool_call(tool_name="skill_manage", args={"action": "create", "name": "n"}) is None,
      "create action passes")

# ── 9. 名单持久化 + 列表 API 一致
g.set_tier("explicit-deny-probe-skill", "deny")
rows = {row["name"]: row for row in g.list_skills()}
check(rows.get("explicit-deny-probe-skill", {}).get("tier") == "deny", "list shows explicit deny")
check(rows.get(user_sample, {}).get("class") != "agent", "user sample not classified agent")
ag = [n for n in rows if rows[n]["class"] == "agent"]
check(len(ag) > 0, f"agent class nonempty ({len(ag)})")
g.set_tier("explicit-deny-probe-skill", None)

# ── 10. 线程身份兜底: ContextVar 停留在默认 foreground 时, bg-review 线程仍按后台处理
#     (2026-10-17 真实事故回归: fork 的 copy_context 在 turn_context 设 origin 之前快照,
#      钩子读到 foreground, pinned hub 件 comfyui 被自我改进静默改写、零审计)
import threading

def _run_on(fake_name, fn):
    box = {}
    def _j():
        box['r'] = fn()
    th = threading.Thread(target=_j, name=fake_name, daemon=True)
    th.start(); th.join()
    return box['r']

# 不 set origin —— ContextVar 保持默认 "foreground", 只有线程名暴露后台身份
r = _run_on("bg-review", lambda: g._on_pre_tool_call(
    tool_name="skill_manage", args={"action": "patch", "name": user_sample}))
check(r and r.get("action") == "block", "bg-review thread w/ stale foreground origin still blocked")
r = _run_on("bg-review", lambda: g._on_pre_tool_call(
    tool_name="skill_manage", args={"action": "delete", "name": agent_sample}))
check(r and r.get("action") == "block", "bg-review thread delete blocked (strictest tier)")
r = _run_on("bg-review", lambda: g._on_pre_tool_call(
    tool_name="skill_manage", args={"action": "patch", "name": agent_skills[0]}))
check(r is None, "bg-review thread w/ stale origin: agent-created still passes")
r = _run_on("worker-77", lambda: g._on_pre_tool_call(
    tool_name="skill_manage", args={"action": "patch", "name": user_sample}))
check(r is None, "non-bg thread name keeps fg semantics (no false positives)")


# ── 批量形态回归: skill_manage(operations=[...]) 顶层无 action/name ——
# 真实事故 2026-10-17 05:02: bg review 用批量 patch 给用户所有的第三方 skill
# 追加了三行, v1 与 v0.2.0 的钩子都在 `if not name` 处早退, 零审计。
r = _run_on("bg-review", lambda: g._on_pre_tool_call(
    tool_name="skill_manage", args={"operations": [{"action": "patch", "name": user_sample,
                                    "old_string": "x", "new_string": "y"}]}))
check(r and r.get("action") == "block", "bg-review batch patch user-owned blocked (05:02 incident shape)")

r = _run_on("bg-review", lambda: g._on_pre_tool_call(
    tool_name="skill_manage", args={"operations": [{"action": "patch", "name": agent_skills[0],
                                    "old_string": "x", "new_string": "y"}]}))
check(r is None, "bg-review batch patch agent-created passes")

r = _run_on("bg-review", lambda: g._on_pre_tool_call(
    tool_name="skill_manage", args={"operations": [
        {"action": "patch", "name": agent_skills[0], "old_string": "x", "new_string": "y"},
        {"action": "patch", "name": user_sample, "old_string": "x", "new_string": "y"}]}))
check(r and r.get("action") == "block", "mixed batch vetoed atomically (one user-owned op kills call)")

r = _run_on("bg-review", lambda: g._on_pre_tool_call(
    tool_name="skill_manage", args={"operations": [{"action": "delete", "name": agent_sample}]}))
check(r and r.get("action") == "block", "bg-review batch delete blocked (delete tier, every origin)")

r = _run_on("bg-review", lambda: g._on_pre_tool_call(
    tool_name="skill_manage", args={"operations": [{"action": "patch", "old_string": "x", "new_string": "y"}]}))
check(r and r.get("action") == "block", "bg-review batch op w/o explicit name fails closed")

# 前台批量: 用户指令语义, 放行且不写审计(与单发前台一致)
r = g._on_pre_tool_call(tool_name="skill_manage",
                        args={"operations": [{"action": "patch", "name": user_sample, "old_string": "x", "new_string": "y"}]})
check(r is None, "foreground batch patch passes (user-directed)")

# 空 operations / 非 list 防御: 不因批量分支误伤
check(g._on_pre_tool_call(tool_name="skill_manage", args={"operations": []}) is None, "empty operations list untouched")
print("\n===", "ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}", "===")
sys.exit(1 if fails else 0)
