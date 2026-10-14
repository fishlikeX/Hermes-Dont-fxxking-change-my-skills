// 别改我的技能！ — desktop sidebar page for the dont-change-my-skills plugin.
// Pure-JS ESM, hot-loaded from <hermes-home>/desktop-plugins/ by the desktop
// runtime loader (bare imports: @hermes/plugin-sdk, react only).
// HARD RULES learned the hard way (owner caught the page blank twice):
//  - use React.createElement (h) — jsx(type, config, key) takes children INSIDE
//    config; positional children render an empty element (the blank-page bug).
//  - avoid react-query hooks here; useState/useEffect against ctx.rest is proven.
//  - every optional SDK seam (ctx.i18n.*) gets a capability check — one missing
//    API must never throw inside register() and blank the whole plugin.
// Locale: prefers the official ctx.i18n seam; on builds without it, picks the
// bundle from navigator.language and stays there until restart.
import {
  host,
  ROUTES_AREA, SIDEBAR_NAV_AREA, PALETTE_AREA,
} from '@hermes/plugin-sdk'
import { createElement as h, useCallback, useEffect, useState } from 'react'

const ID = 'dont-change-my-skills'
const PATH = '/skill-guard'

const BUNDLES = {
  en: {
    nav: "Don't change my skills!",
    title: "Don't fxxking change my skills!",
    intro: 'Background self-improvement may only touch AGENT skills by default. Flip a row to override.',
    stats: '{n} skills · auto {a} · allow {al} · deny {d} · {b} background writes blocked{r}',
    loading: 'loading skills…',
    backendError: 'backend error: ',
    auditHead: 'recent guard activity',
    archived: 'archived',
    pinned: 'PIN',
    tierHintAllow: 'background review MAY edit this skill',
    tierHintAuto: 'guard default: only agent-created skills are editable',
    tierHintDeny: 'background review must NOT touch this skill',
  },
  zh: {
    nav: '别改我的技能！',
    title: '别改我的技能！',
    intro: '后台自我改进默认只能改 AGENT 自产 skill，逐行拨开关可覆盖。',
    stats: '共 {n} 个 skill · auto {a} · allow {al} · deny {d} · 迄今拦截后台改写 {b} 次{r}',
    loading: '加载技能清单…',
    backendError: '后端错误：',
    auditHead: '最近的守卫动作',
    archived: '已归档',
    pinned: '钉',
    tierHintAllow: '后台评审【可以】改这个 skill',
    tierHintAuto: '守卫默认：只放行 agent 自产的 skill',
    tierHintDeny: '后台评审【禁止】碰这个 skill',
  },
}

const CLASS_LABEL = {
  agent: 'AGENT', user: 'USER', bundled: 'BUNDLED', hub: 'HUB',
  external: 'EXTERNAL', gone: 'GONE',
}
const CLS_COLOR = {
  agent: 'var(--ui-accent)', user: 'var(--ui-text-secondary)',
  bundled: 'var(--ui-stroke-secondary)', hub: 'var(--ui-stroke-secondary)',
  external: 'var(--ui-stroke-secondary)', gone: 'var(--ui-stroke-secondary)',
}
const TIERS = ['allow', 'auto', 'deny']

const cellStyle = {
  display: 'flex', alignItems: 'center', gap: 8,
  padding: '6px 4px', borderBottom: '1px solid var(--ui-stroke-secondary)',
}

function TierChips({ row, pending, onPick, tr }) {
  return h('div', { style: { display: 'flex' } }, TIERS.map((tier) => {
    const on = row.tier === tier
    return h('button', {
      key: tier,
      type: 'button',
      title: tr('tierHint' + tier[0].toUpperCase() + tier.slice(1)),
      disabled: pending,
      onClick: () => onPick(row.name, tier),
      style: {
        padding: '2px 10px', fontSize: 11, cursor: 'pointer', marginLeft: 4,
        borderRadius: 999, background: 'transparent',
        border: '1px solid ' + (on ? 'var(--ui-accent)' : 'var(--ui-stroke-secondary)'),
        color: on ? 'var(--ui-accent)' : 'var(--ui-text-quaternary)',
      },
    }, tier)
  }))
}

function Page({ ctx, tr }) {
  const [rows, setRows] = useState(null)
  const [audit, setAudit] = useState(null)
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(null)
  const [loadedAt, setLoadedAt] = useState(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const [r, a] = await Promise.all([
        ctx.rest('/skills'),
        ctx.rest('/audit?lines=8').catch(() => null),
      ])
      setRows(Array.isArray(r) ? r : [])
      setAudit(a)
    } catch (e) {
      setError(String((e && e.message) || e))
    } finally {
      setLoadedAt(new Date().toLocaleTimeString())
    }
  }, [ctx])

  useEffect(() => { load() }, [load])

  const pick = useCallback(async (skill, tier) => {
    setPending(skill)
    try {
      await ctx.rest('/tier', { method: 'POST', body: { skill, tier } })
      await load()
    } catch (e) {
      setError(skill + ' -> ' + tier + ': ' + String((e && e.message) || e))
    } finally {
      setPending(null)
    }
  }, [ctx, load])

  const list = rows || []
  const counts = list.reduce((a, r) => { a[r.tier] = (a[r.tier] || 0) + 1; return a }, {})
  const blocked = (audit && audit.blocked_total) || 0
  const tail = (audit && audit.tail) || []
  const statsLine = tr('stats')
    .replace('{n}', list.length).replace('{a}', counts.auto || 0)
    .replace('{al}', counts.allow || 0).replace('{d}', counts.deny || 0)
    .replace('{b}', blocked)
    .replace('{r}', loadedAt ? ' · refreshed ' + loadedAt : '')

  return h('div', {
    style: { padding: 16, height: '100%', overflow: 'auto', color: 'var(--ui-text-primary)' },
  },
    h('h2', { style: { margin: '0 0 2px', fontSize: 16 } }, tr('title')),
    h('div', {
      style: { fontSize: 12, color: 'var(--ui-text-secondary)', marginBottom: 10 },
    }, tr('intro')),
    error
      ? h('div', {
          style: {
            padding: '8px 10px', marginBottom: 10, fontSize: 12, color: 'var(--ui-accent)',
            border: '1px solid var(--ui-stroke-secondary)', borderRadius: 6, wordBreak: 'break-word',
          },
        }, tr('backendError') + error)
      : null,
    rows === null && !error
      ? h('div', { style: { padding: '8px 0', fontSize: 12, color: 'var(--ui-text-quaternary)' } }, tr('loading'))
      : h('div', {
          style: { fontSize: 12, color: 'var(--ui-text-quaternary)', marginBottom: 8 },
        }, statsLine),
    h('div', { style: { maxWidth: 760 } }, list.map((r) => h('div', {
      key: r.name,
      style: cellStyle,
    },
      h('span', {
        style: {
          fontSize: 10, fontWeight: 700, letterSpacing: '.03em', minWidth: 60,
          color: CLS_COLOR[r.class] || 'var(--ui-text-quaternary)',
        },
      }, CLASS_LABEL[r.class] || r.class),
      h('span', {
        style: { flex: 1, color: 'var(--ui-text-primary)', fontSize: 13, wordBreak: 'break-word' },
      },
        r.name,
        r.pinned ? h('span', { style: { color: 'var(--ui-accent)', marginLeft: 6, fontSize: 10 } }, tr('pinned')) : null,
        r.archived ? h('span', { style: { color: 'var(--ui-text-quaternary)', marginLeft: 6, fontSize: 10 } }, tr('archived')) : null,
      ),
      h(TierChips, { key: 'chips', row: r, pending: pending === r.name, onPick: pick, tr }),
    ))),
    tail.length
      ? h('div', { style: { marginTop: 16, maxWidth: 760 } },
          h('div', { style: { fontSize: 11, color: 'var(--ui-text-quaternary)', marginBottom: 4 } }, tr('auditHead')),
          ...tail.map((ln, i) => h('div', {
            key: i,
            style: { fontFamily: 'monospace', fontSize: 11, color: 'var(--ui-text-secondary)', whiteSpace: 'pre-wrap' },
          }, ln)),
        )
      : null,
  )
}

export default {
  id: ID,
  name: "Don't change my skills! · 别改我的技能！",
  register(ctx) {
    // Capability-check the i18n seam — installed builds predate parts of it.
    const i18n = ctx.i18n
    let hasI18n = !!(i18n && typeof i18n.register === 'function' && typeof i18n.t === 'function')
    if (hasI18n) {
      try { i18n.register(BUNDLES) } catch (e) { hasI18n = false }
    }

    const guessBundle = () => {
      if (hasI18n) {
        try {
          const v = i18n.t('title')
          if (typeof v === 'string' && v) return v
        } catch (e) { /* fall through to navigator */ }
      }
      const lang = (typeof navigator !== 'undefined' && navigator.language) || 'en'
      return lang.toLowerCase().startsWith('zh') ? 'zh' : 'en'
    }
    const makeTr = () => {
      if (hasI18n) {
        return (key) => {
          try {
            const v = i18n.t(key)
            return typeof v === 'string' && v ? v : (BUNDLES.en[key] || key)
          } catch (e) { return BUNDLES.en[key] || key }
        }
      }
      const b = BUNDLES[guessBundle()] || BUNDLES.en
      return (key) => b[key]
    }

    const mount = () => {
      const tr = makeTr()
      ctx.registerMany([
        { id: 'page', area: ROUTES_AREA, data: { path: PATH }, render: () => h(Page, { ctx, tr }) },
        { id: 'nav', area: SIDEBAR_NAV_AREA, data: { path: PATH, label: tr('nav'), codicon: 'shield' } },
        { id: 'open', area: PALETTE_AREA, data: { id: 'skill-guard.open', title: tr('nav'), run: () => host.navigate(PATH) } },
      ])
    }
    mount()
    if (hasI18n && typeof i18n.onLocaleChange === 'function') {
      i18n.onLocaleChange(() => mount())
    }
  },
}
