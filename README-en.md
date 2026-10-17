<div align="center">

# Don't fxxking change my skills!

**A [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin that restores the
skill-ownership guard removed upstream by `e3d2e57c9`
([#134289](https://github.com/NousResearch/hermes-agent/pull/134289)) — the background
self-improvement fork may only touch skills the agent itself created.**

A per-skill allow/deny panel (Desktop sidebar + CLI) and a permanent audit log of every verdict.

![Plugin](https://img.shields.io/badge/Hermes-plugin-7c3aed)
![Hook](https://img.shields.io/badge/hook-pre__tool__call-3b82f6)
![Deps](https://img.shields.io/badge/python__deps-none-22c55e)
![Network](https://img.shields.io/badge/network__calls-zero-06b6d4)
![Validate](https://img.shields.io/badge/plugins__validate-pass-16a34a)
![Tests](https://img.shields.io/badge/tests-16_PASS-6366f1)
![License](https://img.shields.io/badge/License-MIT-f97316)

[中文说明](README.md)

</div>

---

## Why

Hermes runs a background "self-improvement" review that distills lessons after sessions and
rewrites skills. Older upstream versions carried an ownership guard: **review may only patch
skills the agent created; user-authored, hub-installed, bundled and pinned skills are
write-protected.**

Upstream `e3d2e57c9` removed that guard from the content-write path (rationale: ~77% of review
writes bounced off the ownership rules). Since then, review can patch any skill — including your
strict-constraint SKILL.md files, where injected external text dilutes the constraints and
silently drifts the SOP. Newly added `references/` files no longer even require
read-before-write.

This plugin restores the guard and hands the verdict — and every override — back to you.

## Behavior spec

The verdict happens inside a `pre_tool_call` hook, scoped to `skill_manage` content writes
(`patch` / `write_file` / `remove_file`):

| Case | Default (`auto`) | Per-skill `allow` | Per-skill `deny` |
|---|---|---|---|
| Agent-created skill (`.usage.json`: `created_by=="agent"` or `agent_created==true`) | ✅ review may patch | ✅ | ❌ blocked |
| User-authored / hub / bundled / pinned / **no record** (conservatively user-owned) | ❌ blocked | ✅ unblocked | ❌ blocked |
| Foreground session (user-instructed, in chat) | ✅ always passes | ✅ | ✅ |
| `delete` (any tier, any origin) | ❌ always blocked (strictest) | ❌ | ❌ |

- Ownership comes from `tools/skill_usage._is_curator_managed_record` — `created_by` is a
  curator-management opt-in flag, not proof of authorship; when missing it defaults
  **conservatively to user-owned** (fewer writes beats one wrong write).
- Block messages reproduce the old upstream semantics, steering review toward a fork skill or
  `Nothing to save.`
- Every verdict is appended to the plugin's own audit log (origin tier, evidence, result) —
  checkable after the fact, by third parties, not just by the plugin's own word.

## Architecture

```
~/.hermes/plugins/dont-change-my-skills/     # Python backend (the part that blocks)
  plugin.yaml                                # provides_hooks: pre_tool_call
  __init__.py                                # hook + tier engine + CLI subcommand
  guard.json                                 # list: skill -> allow|deny|auto (created on demand)
  dashboard/manifest.json + plugin_api.py    # list & tier API under /api/plugins/<id>/

~/.hermes/desktop-plugins/dont-change-my-skills/
  plugin.js                                  # Desktop sidebar page
```

The Desktop page is a remote control for the list — **it contains no decision logic**. Without
it open, the guard runs at full strength.

## Install

Prerequisite: [Hermes Agent](https://github.com/NousResearch/hermes-agent) installed. Zero Python
dependencies, zero network access.

```bash
hermes plugins install fishlikeX/Hermes-Dont-fxxking-change-my-skills --enable
hermes gateway restart          # activate the hook in the running gateway
```

Deep link (one click in the Desktop app):
[Install in Hermes](hermes://plugin/install?repo=fishlikeX/Hermes-Dont-fxxking-change-my-skills&enable=1)

Clone-based alternative: `git clone` this repo, then `python install.py` (resolves
`$HERMES_HOME`, idempotent, preserves config newline style; refuses to rewrite anything when
there is no `plugins:` block instead of guessing).

Self-check with `hermes plugins validate <dir>`. Current state: `Validation passed`,
`security scan — safe`; one known ⚠ (catalog rule 9 — the plugin reuses internal surfaces like
`tools.skill_usage`, unavoidable while restoring upstream's own removed guard; will switch if a
public seam lands).

## Usage

```bash
hermes skill-guard list          # every skill: ownership class + current tier
hermes skill-guard deny <skill>  # explicit block (overrides origin-based classification)
hermes skill-guard allow <skill> # explicitly let background review edit
hermes skill-guard reset <skill> # back to auto
hermes skill-guard status        # load state + tail of the audit log
```

The Desktop sidebar page ("别改我的技能！") exposes the same list as tri-state switches.
An empty list after install = pure auto mode: agent-created skills stay self-improvable,
everything else is protected — your existing behavior is unchanged until you flip something.

## Trust boundary

Verify any plugin's capability surface before enabling it. Ours, in full:

| Dimension | Reality |
|---|---|
| Network | No outbound requests (no `urllib` / `requests` / `socket` / `subprocess` in source) |
| Credentials | Never reads config.yaml, environment, tokens or keys |
| Writes | Only `guard.json` + `audit.log` inside its own directory, created on demand |
| Veto scope | Votes only on `skill_manage` `patch` / `write_file` / `remove_file`; never touches terminals or message delivery |
| Foreground impact | **None** — user-instructed edits always pass through |
| Failure direction | Classifier errors → background path fails closed (block); the hook itself never raises |
| Uninstall | `hermes plugins remove dont-change-my-skills`; deleting the plugin folder leaves nothing behind — no source patches, no daemon |

Verdicts run in the host process (`plugins.isolation: host`), the inherent shape of intercepting
hooks: it can veto `skill_manage`, so evaluate it as "can read parameters visible in the host" —
it reads `{action, name}` from the call and does string comparison plus a local ledger lookup.

## Known classification seam (measured, worth knowing)

`created_by` is the curator's management opt-in flag, not authorship proof. In practice a
user-authored skill can end up stamped `created_by: "agent"` in the ledger (via `curator adopt`
or an early stamp at creation time), and pure auto mode then treats it as agent-owned and lets
background review through.

**Countermeasure:** the explicit list overrides auto — on discovering a misclassification,
`hermes skill-guard deny <name>` seals it in one command, or flip the row to deny in the panel.
The flag is a first-pass classifier; the per-skill list is the final word.

## 🔒 v0.2.0: double-signal background identity (why you should upgrade)

v1 detected "is this write from the self-improvement fork?" via a single
ContextVar. Measured hole: the review fork snapshots the parent context BEFORE
the write-origin marker is written into that ContextVar, so the hook always read
the default "foreground" — background writes passed as foreground, **bypassing
even an explicit deny**, with zero audit lines. Our own first field incident
proves it: a pinned, hub-installed skill was silently patched by the reviewer
while audit.log stayed empty.

v0.2.0 fixes it: a write counts as background if EITHER signal fires — the
write-origin ContextVar, or the current thread being named `bg-review` (the
review worker name, fixed at thread creation, cannot drift). deny/auto/allow now
actually get their turn. The regression suite upgraded too: new cases hit the
hook on a real same-named thread with the ContextVar stuck at its default — the
exact incident shape old tests could not see. 20/20 green.

## 🔒 v0.2.1: batch operations are no longer a back door (v0.2.0 users, upgrade too)

`skill_manage` accepts a batch shape: `operations=[{...}, {...}]` — no top-level
`action`, no `name`. Both v1 and v0.2.0 hooks returned early at the "cannot tell
which skill this targets" guard, so **a single batch call could write to any
skill, bypassing the guard completely, again with zero audit lines**. Not a
theoretical adversary: the day v0.2.0 shipped, our own background reviewer used
this exact shape to append to a third-party skill while audit.log stayed empty.

v0.2.1 fixes it: the hook now recognizes the batch shape and vetoes per operation,
applying the same verdict as the equivalent single call (delete = every origin;
deny list; user-owned skills in background; unnamed entries fail closed). Batches
apply atomically, so blocking one operation blocks the whole call — matching the
guard's semantics exactly. The regression suite grew to 26 cases, including the
incident shape (bg thread + batch patch on a user-owned skill, mixed-batch atomic
veto, unnamed-op fail-closed, foreground batches unaffected).


## Status

- [x] Behavior spec agreed with the project owner (2026-10-14, five rules)
- [x] Python hook + tier engine (16 unit assertions green, re-run after every change)
- [x] CLI (`hermes skill-guard list|allow|deny|reset|status`)
- [x] Desktop panel (sidebar page + tri-state switches, hot-loaded from `desktop-plugins/`)
- [x] Triple acceptance: background blocked / foreground untouched / hook-error fails closed
- [x] Passes the official `hermes plugins validate` gate (`security scan — safe`)

## License

MIT
