/**
 * Exact structural port of CineForge-Storyboard-Studio-v2 ExportsPage (pagesOps.tsx)
 * + mockProject.exports catalog — PHASE A ARTIFACTS layout (Screenshot 2026-07-11 172805),
 * readiness banner, export card grid, seeded recent packages.
 *
 * DOM hierarchy matches ZIP prototype + Screenshot 2026-07-11 172805:
 * PageTitle → export-banner → export-layout (export-grid | history-panel).
 *
 * Production boundary:
 * - Storyboard JSON → live GET exportJsonUrl /stories/{id}/export.json
 * - Shot List CSV → live GET exportShotListCsvUrl /stories/{id}/shot-list.csv
 * - PDF / EDL / render package → disabled with factual unavailability reasons
 * - Remaining catalog packages → planning UI only; no binary media or render
 */
import { useMemo, useState } from 'react'
import { api, exportJsonUrl, exportShotListCsvUrl } from '../../api/client'
import {
  Button,
  Icon,
  Modal,
  PageTitle,
  Progress,
  StatusPill,
  type IconName,
} from '../proto/ui'
import { demoExportsFixture, demoExportsPackageHistory } from '../demoPhaseA'
import { useStudio } from '../StudioState'
import { countShots, toProtoProject } from '../proto/adapter'

type ExportCard = {
  id: string
  name: string
  description: string
  format: string
  requirement: string
  lastExport: string
  version: string
  ready: boolean
  /** True only when a live download endpoint exists. */
  live: boolean
  reason?: string
  href?: string
}

type HistoryItem = { name: string; time: string; status: string }

const DEMO_LAST_EXPORT = demoExportsFixture.lastExport
const DEMO_VERSION = demoExportsFixture.version

const PDF_DISABLED_REASON =
  'PDF export is not available — no PDF endpoint is exposed. Planning package UI only.'
const OUTLINE_DISABLED_REASON =
  'Chapter / Scene Outline download is not exposed — planning catalog only; no outline endpoint.'
const GAPS_DISABLED_REASON =
  'Model Gap Report download is not exposed — planning catalog only; no gap-report endpoint.'

/** Icon selection matches prototype pagesOps.tsx export grid. */
function exportIcon(item: ExportCard): IconName {
  if (item.format.includes('CSV') && !item.format.includes('PDF')) return 'grid'
  if (item.format.includes('JSON') && !item.format.includes('ZIP')) return 'layers'
  if (item.name.includes('Voice')) return 'mic'
  if (item.name.includes('Image') || item.name.includes('Animatic')) return 'image'
  if (item.id === 'edl' || item.format === 'EDL') return 'film'
  return 'download'
}

function gateFailed(
  gates: Array<{ label: string; pass: boolean; reason: string }>,
  ...codes: string[]
): string | null {
  const hit = gates.find((g) => codes.includes(g.label) && !g.pass)
  return hit ? hit.reason : null
}

export function ExportsPage() {
  const { data, readiness, navigate, setMessage } = useStudio()
  const [scope, setScope] = useState('Full project')
  const [running, setRunning] = useState('')
  const [history, setHistory] = useState<HistoryItem[]>(() => [...demoExportsPackageHistory])
  const [blocked, setBlocked] = useState<ExportCard | null>(null)

  const view = useMemo(() => (data ? toProtoProject(data, readiness) : null), [data, readiness])

  if (!data || !view) return null

  const { gates, readinessPct } = view
  const failing = gates.filter((g) => !g.pass)
  const shotCount = countShots(data.chapters)
  const links = api.exportLinks(data.story.id)
  const jsonUrl = links.json_url || exportJsonUrl(data.story.id)
  const csvUrl = links.shot_list_csv_url || exportShotListCsvUrl(data.story.id)

  const voiceGap = gateFailed(gates, 'voice_coverage')
  const characterGap = gateFailed(gates, 'character_approval')
  const imageGap = gateFailed(gates, 'starting_images', 'starting_image_requirements')
  const continuityGap = gateFailed(gates, 'continuity')
  const modelGap = gateFailed(gates, 'model_gap', 'model_recommendations')
  const blockedShot = gateFailed(gates, 'blocked_shot')

  // Catalog order/names/formats/descriptions match mockProject.exports (screenshot 172805).
  // Ready/Blocked pills follow planning readiness like the prototype; live download is only JSON + CSV.
  // PDF / outline / gap report stay non-live (no endpoint). Render is never offered.
  const cards: ExportCard[] = [
    {
      id: 'pdf',
      name: 'Full Storyboard PDF',
      description: 'Review-ready visual storyboard',
      format: 'PDF',
      // REF shows Ready when shot hierarchy is present; download stays non-live (no PDF endpoint).
      requirement: shotCount > 0 ? 'All shot data present' : 'PDF export is a future phase',
      lastExport: history.find((h) => h.name === 'Full Storyboard PDF')?.time ?? DEMO_LAST_EXPORT,
      version: DEMO_VERSION,
      ready: shotCount > 0,
      live: links.pdf_available === true,
      reason: PDF_DISABLED_REASON,
    },
    {
      id: 'json',
      name: 'Storyboard JSON',
      description: 'Canonical structured Phase A package',
      format: 'JSON',
      requirement: 'Valid hierarchy',
      lastExport: history.find((h) => h.name === 'Storyboard JSON')?.time ?? DEMO_LAST_EXPORT,
      version: DEMO_VERSION,
      ready: true,
      live: true,
      href: jsonUrl,
    },
    {
      id: 'outline',
      name: 'Chapter / Scene Outline',
      description: 'Narrative hierarchy and timing',
      format: 'PDF · DOCX',
      requirement: 'Story structure present',
      lastExport: history.find((h) => h.name === 'Chapter / Scene Outline')?.time ?? DEMO_LAST_EXPORT,
      version: DEMO_VERSION,
      // Visual Ready when hierarchy exists (demo always has chapters); download not live.
      ready: data.chapters.length > 0,
      live: false,
      reason: OUTLINE_DISABLED_REASON,
    },
    {
      id: 'csv',
      name: 'Shot List CSV',
      description: `All ${shotCount} generation units`,
      format: 'CSV',
      requirement: 'Durations reconcile',
      lastExport: history.find((h) => h.name === 'Shot List CSV')?.time ?? DEMO_LAST_EXPORT,
      version: DEMO_VERSION,
      ready: true,
      live: true,
      href: csvUrl,
    },
    {
      id: 'narration',
      name: 'Narration Script',
      description: 'Timed narration and voice assignments',
      format: 'DOCX · TXT',
      requirement: voiceGap ? 'Resolve 2 voice gaps' : 'All shots have narration',
      lastExport: 'Never',
      version: '—',
      ready: !voiceGap,
      live: false,
      reason: voiceGap
        ? `Narration script blocked — ${voiceGap}`
        : 'Narration script export is not implemented yet — no DOCX/TXT endpoint is exposed.',
    },
    {
      id: 'bible',
      name: 'Character Bible',
      description: 'Identity and wardrobe package',
      format: 'PDF',
      requirement: characterGap ? 'Approve Maya and Jordan' : 'Character references approved',
      lastExport: 'Never',
      version: '—',
      ready: !characterGap,
      live: false,
      reason: characterGap
        ? `Character bible blocked — ${characterGap}`
        : 'Character bible package export is not implemented yet — no package endpoint is exposed.',
    },
    {
      id: 'voices',
      name: 'Voice Assignment Report',
      description: 'Coverage, source, and consent',
      format: 'PDF · CSV',
      requirement: voiceGap || characterGap ? 'Jordan consent required' : 'Voice coverage complete',
      lastExport: 'Never',
      version: '—',
      ready: !voiceGap && !characterGap,
      live: false,
      reason:
        voiceGap || characterGap
          ? `Voice assignment report blocked — ${voiceGap ?? characterGap}`
          : 'Voice assignment report export is not implemented yet — no report endpoint is exposed.',
    },
    {
      id: 'images',
      name: 'Starting-Image Manifest',
      description: 'Prompts, candidates, and approvals',
      format: 'JSON · CSV',
      requirement: imageGap ? 'Approve remaining images' : 'Starting images present',
      lastExport: 'Never',
      version: '—',
      ready: !imageGap,
      live: false,
      reason: imageGap
        ? `Starting-image manifest blocked — ${imageGap}`
        : 'Starting-image manifest export is not implemented yet — no manifest endpoint is exposed.',
    },
    {
      id: 'prompts',
      name: 'Prompt Package',
      description: 'Image, video, negative, and continuity prompts',
      format: 'ZIP · JSON',
      requirement: blockedShot ? 'Resolve blocked shot' : 'Prompt packages present',
      lastExport: 'Never',
      version: '—',
      ready: !blockedShot,
      live: false,
      reason: blockedShot
        ? `Prompt package blocked — ${blockedShot}`
        : 'Prompt package export is not implemented yet — no package endpoint is exposed.',
    },
    {
      id: 'gaps',
      name: 'Model Gap Report',
      description: 'Installed and missing dependencies',
      format: 'PDF · JSON',
      // REF shows Ready for Model Gap Report even with model inventory open (report itself is generable).
      requirement: modelGap ? 'Model inventory recorded' : 'Model inventory complete',
      lastExport: history.find((h) => h.name === 'Model Gap Report')?.time ?? 'Yesterday · 5:08 PM',
      version: DEMO_VERSION,
      ready: true,
      live: false,
      reason: GAPS_DISABLED_REASON,
    },
    {
      id: 'workflow',
      name: 'Workflow Assignment Report',
      description: 'Per-shot deterministic workflow plan',
      format: 'PDF · CSV',
      requirement: 'Workflow assignment incomplete',
      lastExport: 'Never',
      version: '—',
      ready: false,
      live: false,
      reason:
        'Workflow assignment report export is not implemented yet — no assignment endpoint is exposed.',
    },
    {
      id: 'continuity',
      name: 'Continuity Report',
      description: 'Links and visual consistency checks',
      format: 'PDF',
      requirement: continuityGap ? 'Repair continuity links' : 'Continuity links valid',
      lastExport: 'Never',
      version: '—',
      ready: !continuityGap,
      live: false,
      reason: continuityGap
        ? `Continuity report blocked — ${continuityGap}`
        : 'Continuity report export is not implemented yet — no continuity endpoint is exposed.',
    },
  ]

  const generate = (item: ExportCard) => {
    if (!item.ready) {
      setBlocked(item)
      setMessage(item.reason ?? `${item.name} is blocked — package unavailable`)
      return
    }
    if (item.live && item.href) {
      setRunning(item.id)
      window.setTimeout(() => {
        setRunning('')
        // Live download against the storyboard export API — no render or queue started.
        window.open(item.href, '_blank', 'noopener,noreferrer')
        setHistory((prev) => [{ name: item.name, time: 'Just now', status: 'Ready' }, ...prev])
        setMessage(`${item.name} download started from the live API (${scope}).`)
      }, 350)
      return
    }
    // Ready in planning UI but no live endpoint — record local history only (prototype honesty).
    setRunning(item.id)
    window.setTimeout(() => {
      setRunning('')
      setHistory((prev) => [{ name: item.name, time: 'Just now', status: 'Ready' }, ...prev])
      setMessage(
        `${item.name} recorded in local package history only (${scope}). No binary media, PDF bytes, or render package was created — live downloads remain JSON and CSV.`,
      )
    }, 350)
  }

  return (
    <div className="page">
      <PageTitle
        eyebrow="PHASE A ARTIFACTS"
        title="Exports"
        description="Package the current structured production plan for review, handoff, or archive."
        aside={
          <div className="page-actions">
            <label className="inline-select">
              Scope
              <select value={scope} onChange={(event) => setScope(event.target.value)}>
                <option>Full project</option>
                <option>Chapter 1</option>
                <option>Selected scene</option>
                <option>Approved shots only</option>
              </select>
            </label>
            <Button
              type="button"
              onClick={() =>
                setMessage(
                  'Export behavior: Storyboard JSON and Shot List CSV hit live storyboard export endpoints. PDF, EDL, render packages, and remaining formats stay planning-only — no binary media, rendered video, or external storage is created from this page.',
                )
              }
              icon="spark"
            >
              Export behavior
            </Button>
          </div>
        }
      />

      <div className="export-banner">
        <div>
          <span className="export-ring">{readinessPct}%</span>
          <span>
            <b>Production package readiness</b>
            <small>
              {failing.length
                ? `${failing.length} required gates still block the final manifest`
                : readiness?.ready
                  ? 'Required gates currently pass'
                  : 'Readiness pending from server'}
            </small>
          </span>
        </div>
        <Progress value={readinessPct} />
        <button
          type="button"
          onClick={() => {
            if (failing.length) {
              setMessage(
                `Exact export blockers:\n${failing.map((g) => `• ${g.label}: ${g.reason}`).join('\n')}`,
              )
            } else {
              navigate('overview')
            }
          }}
        >
          View exact blockers <Icon name="arrow" />
        </button>
      </div>

      <div className="export-layout">
        <div className="export-grid">
          {cards.map((item, index) => {
            const isLive = Boolean(item.ready && item.live && item.href)
            const isRunning = running === item.id
            const controlTitle = !item.ready
              ? (item.reason ?? item.requirement)
              : isLive
                ? `Download ${item.format} from live API`
                : (item.reason ?? `${item.name} is planning-only — no live download endpoint`)
            return (
              <article key={item.id}>
                <header>
                  <span className={`export-icon export-${index % 5}`}>
                    <Icon name={exportIcon(item)} />
                  </span>
                  <StatusPill status={item.ready ? 'Ready' : 'Blocked'} />
                </header>
                <h3>{item.name}</h3>
                <p>{item.description}</p>
                <dl>
                  <div>
                    <dt>Format</dt>
                    <dd>{item.format}</dd>
                  </div>
                  <div>
                    <dt>Requirement</dt>
                    <dd>{item.requirement}</dd>
                  </div>
                  <div>
                    <dt>Last export</dt>
                    <dd>{item.lastExport}</dd>
                  </div>
                  <div>
                    <dt>Version</dt>
                    <dd>{item.version}</dd>
                  </div>
                </dl>
                <footer>
                  <span>{scope}</span>
                  <Button
                    type="button"
                    variant={item.ready ? 'primary' : 'secondary'}
                    icon={item.ready ? 'download' : 'lock'}
                    onClick={() => generate(item)}
                    disabled={isRunning}
                    title={controlTitle}
                  >
                    {isRunning ? 'Generating…' : 'Generate export'}
                  </Button>
                </footer>
              </article>
            )
          })}
        </div>

        <aside className="history-panel">
          <header>
            <span className="eyebrow">EXPORT HISTORY</span>
            <h2>Recent packages</h2>
          </header>
          {history.map((entry, index) => (
            <button
              key={`${entry.name}-${index}`}
              type="button"
              onClick={() =>
                setMessage(`${entry.name} was generated this browser session (${scope}).`)
              }
            >
              <span className="history-file">
                <Icon name="download" />
              </span>
              <span>
                <b>{entry.name}</b>
                <small>
                  {entry.time} · {scope}
                </small>
              </span>
              <StatusPill status={entry.status} />
            </button>
          ))}
          <Button type="button" variant="quiet" onClick={() => setHistory([])}>
            Clear local history
          </Button>
          {!history.length ? (
            <p className="history-empty">No exports in this browser session.</p>
          ) : null}
          <div className="prototype-note">
            <Icon name="lock" />
            <p>
              <b>Live package boundary</b>
              JSON and CSV download from the API only. PDF, EDL, and render packages stay disabled.
              No binary media, rendered video, or external storage is created from unavailable
              package types.
            </p>
          </div>
        </aside>
      </div>

      {blocked ? (
        <Modal title={`${blocked.name} is not ready`} onClose={() => setBlocked(null)}>
          <div className="blocked-export">
            <Icon name="warning" size={30} />
            <p>{blocked.reason ?? blocked.requirement}</p>
            <div>
              {failing.slice(0, 4).map((gate) => (
                <span key={gate.label}>
                  <b>{gate.label}</b>
                  <small>{gate.reason}</small>
                </span>
              ))}
              {!failing.length ? (
                <span>
                  <b>Package unavailable</b>
                  <small>{blocked.reason ?? blocked.requirement}</small>
                </span>
              ) : null}
            </div>
            <Button type="button" variant="primary" onClick={() => setBlocked(null)}>
              Return to exports
            </Button>
          </div>
        </Modal>
      ) : null}
    </div>
  )
}
