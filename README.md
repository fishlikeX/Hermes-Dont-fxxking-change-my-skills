<div align="center">

# 别改我的技能！ · Dont fxxking change my skills!

![Plugin](https://img.shields.io/badge/Hermes-plugin-7c3aed)
![Hook](https://img.shields.io/badge/hook-pre__tool__call-3b82f6)
![Deps](https://img.shields.io/badge/python__deps-none-22c55e)
![Network](https://img.shields.io/badge/network__calls-zero-06b6d4)
![Validate](https://img.shields.io/badge/plugins__validate-pass-16a34a)
![Tests](https://img.shields.io/badge/tests-16_PASS-6366f1)
![License](https://img.shields.io/badge/License-MIT-f97316)

[English](README-en.md)

</div>

---

一个 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 插件，还原被上游提交
`e3d2e57c9`（NousResearch/hermes-agent#134289）从后台自我改进 fork 中移除的
**skill 所有权守卫**，并附一块可视化名单面板。

## 为什么需要它 / Why

Hermes 的后台"自我改进"评审会在会话结束后自动沉淀经验、改写 skill。上游旧版本有一条
所有权守卫：**评审只许改 agent 自己创建的 skill；用户手写、用户从 hub 安装、bundled、
pinned 的 skill 一律禁写。**

上游 `e3d2e57c9` 把这条守卫从内容写路径上撤掉了（理由是评审写入约 77% 被所有权规则
弹回），此后评审可以 patch 任何 skill——包括用户自己写的强约束 skill。外部文本混入
约束型 SKILL.md 会稀释其约束力、使其失准，且新加的 `references/` 支持文件连
read-before-write 都不再要求。

本插件把这条守卫以插件形式还原，判定权与覆盖权交还用户。

## 行为规格 / Behavior spec

判定发生在 `pre_tool_call` 钩子内，仅针对 `skill_manage` 的内容写
（patch / write_file / remove_file）：

| 场景 | 默认（auto） | 单独 allow | 单独 deny |
|---|---|---|---|
| agent 自产 skill（`.usage.json` 判据 `created_by=="agent"` 或 `agent_created==true`） | ✅ 评审可改 | ✅ | ❌ 禁改 |
| 用户创建 / hub / bundled / pinned / **无记录**（保守归用户） | ❌ 评审禁改 | ✅ 放行 | ❌ |
| 前台会话（用户当面指示） | ✅ 直通 | ✅ | ✅ |
| `delete`（任何档、任何来源） | ❌ 一律禁止（最严） | ❌ | ❌ |

- 来源判据来自 `tools/skill_usage._is_curator_managed_record`（`created_by` 是
  curator-management 的 opt-in 旗子而非创作证明，缺失时**保守归用户**——宁可少改不误改）。
- 拦截消息复刻旧版语义，提示评审 fork 转向替身 skill 或 `Nothing to save.`。
- 每次判定写入插件审计日志（来源档、判据、结果），事后可查。

## 组成 / Architecture

```
~/.hermes/plugins/dont-change-my-skills/     # Python 后端（真正拦人的）
  plugin.yaml                                # provides_hooks: pre_tool_call
  __init__.py                                # 钩子 + 名单引擎 + CLI 子命令
  guard.json                                 # 名单: skill -> allow|deny|auto
  dashboard/manifest.json + plugin_api.py    # /api/plugins/<id>/ 名单与列表 API

~/.hermes/desktop-plugins/dont-change-my-skills/
  plugin.js                                  # 桌面端侧边栏页「别改我的技能！」
```

桌面端只是名单的遥控面板，**不含任何判定逻辑**；不打开桌面端，保护照常满负荷工作。

## 安装 / Install

前置条件：已安装 [Hermes Agent](https://github.com/NousResearch/hermes-agent)。本插件零 Python 依赖、零网络访问。

```bash
hermes plugins install fishlikeX/Hermes-Dont-fxxking-change-my-skills --enable
hermes gateway restart          # 让钩子在当前网关进程生效
```

一行深链（桌面端点击即装）：
[Install in Hermes](hermes://plugin/install?repo=fishlikeX/Hermes-Dont-fxxking-change-my-skills&enable=1)

想用 clone 方式装：`git clone` 本仓库后执行 `python install.py`（按 `$HERMES_HOME` 定位，幂等，保留 config.yaml 的换行风格；没有 `plugins:` 块时会拒绝改写而不是乱写）。

装完可用 `hermes plugins validate <目录>` 自查。本仓库当前 `Validation passed`、`security scan — safe`；有一项已知 ⚠（catalog 规则 9：插件复用了旧守卫的 `tools.skill_usage` 等内部接口——还原上游被移除的守卫目前绕不开这些判据源，官方公开 seam 落地后会切换）。

## 使用 / Usage

```bash
hermes skill-guard list                 # 全部 skill：来源档 + 当前档位
hermes skill-guard deny <skill>         # 显式禁改（压过 auto 的来源判据）
hermes skill-guard allow <skill>        # 显式放行后台改写
hermes skill-guard reset <skill>        # 回到 auto
hermes skill-guard status               # 装载状态 + 审计日志尾部
```

桌面端侧边栏「别改我的技能！」提供同一份名单的三态开关。安装时名单为空 = 纯 auto 模式：agent 自产可改，其余禁改，不改你的任何既有行为。

## 信任边界 / Trust boundary

启用第三方插件前请自行核对能力面。本插件的能力面如下：

| 维度 | 实况 |
|---|---|
| 网络 | 无任何出站请求（源码无 `urllib` / `requests` / `socket` / `subprocess`） |
| 凭据 | 不读 config.yaml、不读环境变量、不碰 token/key |
| 写入 | 只写自身目录的 `guard.json`（名单）与 `audit.log`（审计），按需创建 |
| 拦截范围 | 只在 `skill_manage` 的 `patch` / `write_file` / `remove_file` 上投票；不碰终端、不碰消息投递 |
| 前台影响 | **零**——前台（用户当面指示）一律直通 |
| 故障方向 | 钩子内分类器异常 → 后台路径 fail-closed（保守禁写），且钩子永不抛异常 |
| 卸载 | `hermes plugins remove dont-change-my-skills`；删掉插件目录即彻底消失，不改 Hermes 源码、不留驻进程 |

判定发生在宿主进程内（`plugins.isolation: host`），这是拦截型钩子的固有形态：它能否决 `skill_manage`，因此也需要按"能读宿主内可见参数"的标准评估——它读到的是 `skill_manage` 的 `{action, name}` 两项，且只做字符串比对与本地台账查询。

## 状态 / Status

- [x] 行为规格与项目所有者对齐（2026-10-14，五条）
- [x] Python 钩子 + 名单引擎（`__init__.py`，16 项单测 + 5 项端到端全绿）
- [x] CLI（`hermes skill-guard list|allow|deny|reset|status`）
- [x] 桌面端面板（侧边栏「别改我的技能！」+ 三态开关，装于 `desktop-plugins/` 热载）
- [x] 三道验收：后台拦截 / 前台不误伤 / 钩子异常 fail-safe（见 test_guard.py）

## ⚠️ 判据裂缝（实测发现，务必知悉）

`created_by` 是 curator 的**纳管旗子**（opt-in），不是创作证明。实践中出现过：用户自研
的 skill 在 usage 台账里被记成 `created_by: "agent"`（疑经 `curator adopt` 或早期创建时
盖戳），默认 auto 模式下因此被误判为"agent 自产"而放行后台改写。

**对策**：显式名单压过 auto——发现误判即 `hermes skill-guard deny <name>` 一条封死，
或在桌面面板把该行拨到 deny。旗子只是初筛，逐 skill 的 allow/deny 才是最终裁决。


## License

MIT
