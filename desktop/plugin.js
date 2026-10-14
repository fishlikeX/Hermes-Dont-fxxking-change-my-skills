// 别改我的技能！ — desktop sidebar page for the dont-change-my-skills plugin.
// Pure-JS ESM, loaded uncompiled by the Hermes desktop app. Only @hermes/plugin-sdk
// + react/jsx-runtime are importable. All colour via theme vars; no hardcode.
//
// Copy is locale-aware: ctx.i18n bundles follow the app's active language
// (en/zh shipped; any other locale falls back to en). React text re-renders
// via usePluginI18n; static contribution labels are re-registered on locale
// change — the documented use of onLocaleChange.
import {
  host,
  ROUTES_AREA, SIDEBAR_NAV_AREA, PALETTE_AREA,
  useQuery, useMutation, useQueryClient,
  usePluginI18n,
} from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'dont-change-my-skills'
const PATH = '/skill-guard'

const BUNDLES = {
  en: {
    nav: 'Skill Guard',
    title: "Don't fxxking change my skills!",
    intro: 'Background self-improvement may only touch AGENT skills by default. Flip a row to override.',
    stats: (n, a, al, d, b) =>
      `${n} skills · auto ${a} · allow ${al} · deny ${d} · ${b} background writes blocked so far`,
    loading: 'loading…',
    backendError: 'backend unavailable — is the Python plugin enabled and gateway running?',
    auditHead: 'recent guard activity',
    archived: 'archived',
    palette: 'Open skill guard',
    tierHint: {
      allow: 'background review MAY edit this skill',
      auto: 'guard default: only agent-created skills are editable',
      deny: 'background review must NOT touch this skill',
    },
  },
  zh: {
    nav: '别改我的技能！',
    title: '别改我的技能！',
    intro: '后台自我改进默认只能改 AGENT 自产 skill，逐行拨开关可覆盖。',
    stats: (n, a, al, d, b) =>
      `共 ${n} 个 skill · auto ${a} · allow ${al} · deny ${d} · 迄今拦截后台改写 ${b} 次`,
    loading: '加载中…',
    backendError: '后端不可用——Python 插件启用了吗？网关在跑吗？',
    auditHead: '最近的守卫动作',
    archived: '已归档',
    palette: '打开技能守卫',
    tierHint: {
      allow: '后台评审【可以】改这个 skill',
      auto: '守卫默认：只放行 agent 自产的 skill',
      deny: '后台评审【禁止】碰这个 skill',
    },
  },
}

// class -> badge tone (background stays the app's; only text/accent used)
const CLASS_LABEL = {
  agent: 'AGENT', user: 'USER', bundled: 'BUNDLED', hub: 'HUB',
  external: 'EXTERNAL', gone: 'GONE',
}
const CLS_COLOR = {
  agent: 'var(--ui-accent)', user: 'var(--ui-text-secondary)',
  bundled: 'var(--ui-text-quaternary)', hub: 'var(--ui-text-quaternary)',
  external: 'var(--ui-text-quaternary)', gone: 'var(--ui-text-quaternary)',
}
const TIERS = ['allow', 'auto', 'deny']

function Row({ ctx, row, qc }) {
  const t = usePluginI18n(ID)
  const mut = useMutation({
    mutationFn: (tier) => ctx.rest('/tier', {
      method: 'POST', body: { skill: row.name, tier },
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skillguard'] }),
  })
  const cells = TIERS.map((tier) => {
    const on = row.tier === tier
    return jsx('button', {
      type: 'button',
      title: t(`tierHint.${tier}`),
      onClick: () => mut.mutate(tier),
      disabled: mut.isPending,
      style: {
        padding: '2px 10px', fontSize: 11, cursor: 'pointer',
        border: `1px solid ${on ? 'var(--ui-accent)' : 'var(--ui-stroke-secondary)'}`,
        borderRadius: 999, marginLeft: 4,
        color: on ? 'var(--ui-accent)' : 'var(--ui-text-quaternary)',
        background: 'transparent',
      },
    }, tier)
  })
  return jsx('div', {
    style: {
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '6px 4px', borderBottom: '1px solid var(--ui-stroke-secondary)',
    },
  }, [
    jsx('span', {
      style: {
        fontSize: 10, fontWeight: 700, letterSpacing: '.03em', minWidth: 60,
        color: CLS_COLOR[row.class] || 'var(--ui-text-quaternary)',
      },
    }, CLASS_LABEL[row.class] || row.class),
    jsx('span', {
      style: { flex: 1, color: 'var(--ui-text-primary)', fontSize: 13, wordBreak: 'break-word' },
    }, [
      row.name,
      row.pinned ? jsx('span', { style: { color: 'var(--ui-accent)', marginLeft: 6, fontSize: 10 } }, '📌') : null,
      row.archived ? jsx('span', { style: { color: 'var(--ui-text-quaternary)', marginLeft: 6, fontSize: 10 } }, t('archived')) : null,
    ]),
    jsx('div', { style: { display: 'flex' } }, cells),
  ], row.name)
}

function Page({ ctx }) {
  const t = usePluginI18n(ID)
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['skillguard'], queryFn: () => ctx.rest('/skills') })
  const audit = useQuery({ queryKey: ['skillguard-audit'], queryFn: () => ctx.rest('/audit?lines=8') })

  const rows = q.data || []
  const counts = rows.reduce((a, r) => { a[r.tier] = (a[r.tier] || 0) + 1; return a }, {})
  const blocked = (audit.data && audit.data.blocked_total) || 0

  return jsxs('div', {
    style: { padding: 16, height: '100%', overflow: 'auto', color: 'var(--ui-text-primary)' },
  }, [
    jsx('h2', { style: { margin: '0 0 2px', fontSize: 16 } }, t('title')),
    jsx('div', {
      style: { fontSize: 12, color: 'var(--ui-text-secondary)', marginBottom: 12 },
    }, t('intro')),
    jsx('div', {
      style: { fontSize: 12, color: 'var(--ui-text-quaternary)', marginBottom: 8 },
    }, t('stats', rows.length, counts.auto || 0, counts.allow || 0, counts.deny || 0, blocked)),
    q.isLoading ? jsx('div', { style: { padding: 20, color: 'var(--ui-text-quaternary)' } }, t('loading')) : null,
    q.isError ? jsx('div', { style: { padding: 12, color: 'var(--ui-accent)' } }, t('backendError')) : null,
    jsx('div', { style: { maxWidth: 720 } },
      rows.map((r) => jsx(Row, { ctx, row: r, qc }, r.name))),
    audit.data && audit.data.tail && audit.data.tail.length
      ? jsxs('div', { style: { marginTop: 16, maxWidth: 720 } }, [
          jsx('div', { style: { fontSize: 11, color: 'var(--ui-text-quaternary)', marginBottom: 4 } }, t('auditHead')),
          ...audit.data.tail.map((ln, i) => jsx('div', {
            style: { fontFamily: 'monospace', fontSize: 11, color: 'var(--ui-text-secondary)', whiteSpace: 'pre-wrap' },
          }, ln, i)),
        ])
      : null,
  ])
}

export default {
  id: ID,
  name: 'Skill Guard · 别改我的技能！',
  register(ctx) {
    ctx.i18n.register(BUNDLES)

    // Static contributions read labels at registration time, so mount through
    // a function and remount on locale switch (official pattern).
    const mount = () => ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: PATH }, render: () => jsx(Page, { ctx }) },
      { id: 'nav', area: SIDEBAR_NAV_AREA, data: { path: PATH, label: ctx.i18n.t('nav'), codicon: 'shield' } },
      { id: 'open', area: PALETTE_AREA, data: { id: 'skill-guard.open', title: ctx.i18n.t('palette'), run: () => host.navigate(PATH) } },
    ])
    mount()
    ctx.i18n.onLocaleChange(() => mount())
  },
}
