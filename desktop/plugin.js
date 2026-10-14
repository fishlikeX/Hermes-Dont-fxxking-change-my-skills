// 别改我的技能！ — desktop sidebar page for the dont-change-my-skills plugin.
// Pure-JS ESM, loaded uncompiled by the Hermes desktop app. Only @hermes/plugin-sdk
// + react/jsx-runtime are importable. All colour via theme vars; no hardcode.
import {
  host,
  ROUTES_AREA, SIDEBAR_NAV_AREA, PALETTE_AREA,
  useQuery, useMutation, useQueryClient,
} from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'dont-change-my-skills'
const PATH = '/skill-guard'

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
const TIER_HINT = {
  allow: 'background review MAY edit this skill',
  auto: 'guard default: only agent-created skills are editable',
  deny: 'background review must NOT touch this skill',
}

function Row({ ctx, row, qc }) {
  const mut = useMutation({
    mutationFn: (tier) => ctx.rest('/tier', {
      method: 'POST', body: { skill: row.name, tier },
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skillguard'] }),
  })
  const cells = TIERS.map((t) => {
    const on = row.tier === t
    return jsx('button', {
      type: 'button',
      title: TIER_HINT[t],
      onClick: () => mut.mutate(t),
      disabled: mut.isPending,
      style: {
        padding: '2px 10px', fontSize: 11, cursor: 'pointer',
        border: `1px solid ${on ? 'var(--ui-accent)' : 'var(--ui-stroke-secondary)'}`,
        borderRadius: 999, marginLeft: 4,
        color: on ? 'var(--ui-accent)' : 'var(--ui-text-quaternary)',
        background: 'transparent',
      },
    }, t)
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
      row.archived ? jsx('span', { style: { color: 'var(--ui-text-quaternary)', marginLeft: 6, fontSize: 10 } }, 'archived') : null,
    ]),
    jsx('div', { style: { display: 'flex' } }, cells),
  ], row.name)
}

function Page({ ctx }) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['skillguard'], queryFn: () => ctx.rest('/skills') })
  const audit = useQuery({ queryKey: ['skillguard-audit'], queryFn: () => ctx.rest('/audit?lines=8') })

  const rows = q.data || []
  const counts = rows.reduce((a, r) => { a[r.tier] = (a[r.tier] || 0) + 1; return a }, {})
  const blocked = (audit.data && audit.data.blocked_total) || 0

  return jsxs('div', {
    style: { padding: 16, height: '100%', overflow: 'auto', color: 'var(--ui-text-primary)' },
  }, [
    jsx('h2', { style: { margin: '0 0 2px', fontSize: 16 } }, '别改我的技能！'),
    jsx('div', {
      style: { fontSize: 12, color: 'var(--ui-text-secondary)', marginBottom: 12 },
    }, 'Background self-improvement may only touch AGENT skills by default. Flip a row to override.'),
    jsx('div', {
      style: { fontSize: 12, color: 'var(--ui-text-quaternary)', marginBottom: 8 },
    }, `${rows.length} skills · auto ${counts.auto || 0} · allow ${counts.allow || 0} · deny ${counts.deny || 0} · ${blocked} background writes blocked so far`),
    q.isLoading ? jsx('div', { style: { padding: 20, color: 'var(--ui-text-quaternary)' } }, 'loading…') : null,
    q.isError ? jsx('div', { style: { padding: 12, color: 'var(--ui-accent)' } },
      'backend unavailable — is the Python plugin enabled and gateway running?') : null,
    jsx('div', { style: { maxWidth: 720 } },
      rows.map((r) => jsx(Row, { ctx, row: r, qc }, r.name))),
    audit.data && audit.data.tail && audit.data.tail.length
      ? jsxs('div', { style: { marginTop: 16, maxWidth: 720 } }, [
          jsx('div', { style: { fontSize: 11, color: 'var(--ui-text-quaternary)', marginBottom: 4 } }, 'recent guard activity'),
          ...audit.data.tail.map((ln, i) => jsx('div', {
            style: { fontFamily: 'monospace', fontSize: 11, color: 'var(--ui-text-secondary)', whiteSpace: 'pre-wrap' },
          }, ln, i)),
        ])
      : null,
  ])
}

export default {
  id: ID,
  name: '别改我的技能！',
  register(ctx) {
    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: PATH }, render: () => jsx(Page, { ctx }) },
      { id: 'nav', area: SIDEBAR_NAV_AREA, data: { path: PATH, label: '别改我的技能！', codicon: 'shield' } },
      { id: 'open', area: PALETTE_AREA, data: { id: 'skill-guard.open', title: 'Open skill guard', run: () => host.navigate(PATH) } },
    ])
  },
}
