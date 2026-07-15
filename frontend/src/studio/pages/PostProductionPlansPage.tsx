import { useEffect, useMemo, useState } from 'react'
import { api, type PostProductionPlanManifest } from '../../api/client'
import { ErrorNotice } from '../../components/Cards'
import { Empty, PageTitle, Section, StatusPill } from '../proto/ui'

type LoadState = 'loading' | 'ready' | 'error'

function formatDate(value: string | null): string {
  if (!value) return '—'
  const timestamp = Date.parse(value)
  if (Number.isNaN(timestamp)) return value
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(timestamp))
}

function formatNumber(value: number | null | undefined, suffix = ''): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—'
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 3 })}${suffix}`
}

function formatBool(value: boolean | null | undefined): string {
  if (value === true) return 'Yes'
  if (value === false) return 'No'
  return '—'
}

function commandPreview(command: string[]): string {
  if (!command.length) return 'No command recorded in this manifest.'
  return command.map((part, index) => `${String(index).padStart(2, '0')}: ${part}`).join('\n')
}

function SummaryCard({ label, value, note }: { label: string; value: string | number; note: string }) {
  return (
    <article className="card">
      <div className="card-heading">
        <span>{label}</span>
      </div>
      <strong>{value}</strong>
      <p>{note}</p>
    </article>
  )
}

function EvidenceRow({ label, value, mono = false }: { label: string; value: string | number; mono?: boolean }) {
  return (
    <div className="disabled-action">
      <strong>{label}</strong>
      <p className={mono ? 'mono' : undefined}>{value}</p>
    </div>
  )
}

function ManifestCard({ manifest }: { manifest: PostProductionPlanManifest }) {
  return (
    <article className="panel">
      <header className="panel-head">
        <div>
          <h2 className="mono">{manifest.plan_id}</h2>
          <p>Read-only local post-production manifest evidence.</p>
        </div>
        <StatusPill status={manifest.state} />
      </header>

      <div className="disabled-action-grid">
        <EvidenceRow label="State" value={manifest.state} />
        <EvidenceRow label="Created" value={formatDate(manifest.created_at)} />
        <EvidenceRow label="Updated" value={formatDate(manifest.updated_at)} />
        <EvidenceRow label="Completed" value={formatDate(manifest.completed_at)} />
        <EvidenceRow label="Command template" value={manifest.command_template_id || '—'} mono />
        <EvidenceRow label="Execution submitted" value={formatBool(manifest.execution_submitted)} />
        <EvidenceRow label="FFmpeg job id" value={manifest.ffmpeg_job_id || '—'} mono />
        <EvidenceRow label="Manifest path" value={manifest.manifest_path || '—'} mono />
        <EvidenceRow label="Output path" value={manifest.output_path || '—'} mono />
        <EvidenceRow label="Input paths" value={manifest.input_paths.length} />
        <EvidenceRow label="Input hashes" value={manifest.input_hashes.length} />
        <EvidenceRow label="Probe count" value={manifest.probe_count} />
        <EvidenceRow label="Target duration" value={formatNumber(manifest.target_duration_sec, ' sec')} />
        <EvidenceRow label="Calculated duration" value={formatNumber(manifest.calculated_duration_sec, ' sec')} />
        <EvidenceRow label="Exact duration preserved" value={formatBool(manifest.exact_duration_preserved)} />
        <EvidenceRow label="Output SHA-256" value={manifest.output_sha256 || '—'} mono />
        <EvidenceRow label="Error message" value={manifest.error_message || '—'} />
      </div>

      <div className="debug-panel" aria-label="Read-only command preview">
        <span className="eyebrow">COMMAND PREVIEW · INERT ARGV TEXT</span>
        <pre>
          <code>{commandPreview(manifest.command)}</code>
        </pre>
      </div>
    </article>
  )
}

export function PostProductionPlansPage() {
  const [plans, setPlans] = useState<PostProductionPlanManifest[]>([])
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true

    api
      .listPostProductionPlans(25)
      .then((manifests) => {
        if (!mounted) return
        setPlans(manifests)
        setError(null)
        setLoadState('ready')
      })
      .catch((caught: unknown) => {
        if (!mounted) return
        setPlans([])
        setError(caught instanceof Error ? caught.message : 'Unable to load post-production plan manifests.')
        setLoadState('error')
      })

    return () => {
      mounted = false
    }
  }, [])

  const summary = useMemo(() => {
    const stateCounts = plans.reduce<Record<string, number>>((counts, plan) => {
      counts[plan.state] = (counts[plan.state] ?? 0) + 1
      return counts
    }, {})
    const stateSummary = Object.entries(stateCounts)
      .map(([state, count]) => `${state}: ${count}`)
      .join(' · ')
    const latestCreatedAt = plans
      .map((plan) => plan.created_at)
      .filter(Boolean)
      .sort((a, b) => Date.parse(b) - Date.parse(a))[0]

    return {
      stateSummary: stateSummary || 'No states recorded',
      executionSubmitted: plans.some((plan) => plan.execution_submitted),
      outputShaCount: plans.filter((plan) => Boolean(plan.output_sha256)).length,
      latestCreatedAt: latestCreatedAt ?? null,
    }
  }, [plans])

  return (
    <div className="studio-page">
      <PageTitle
        eyebrow="OFFLINE POST-PRODUCTION"
        title="Plan manifests"
        description="Read-only evidence from GET /local-post-production/plans. This page does not create plans, execute FFmpeg, submit jobs, render media, or call ComfyUI/GPU."
      />

      <section className="safety-banner" aria-label="Post-production safety boundary">
        <div>
          <strong>Read-only checkpoint</strong>
          <p>
            Existing local manifests are displayed as inert text only. No command input, execution endpoint,
            benchmark, render, download, submission, ComfyUI, or GPU action is exposed here.
          </p>
        </div>
        <StatusPill status="GET only" />
      </section>

      <Section title="Manifest summary" subtitle="Recent offline post-production plan evidence from the backend list endpoint.">
        <div className="grid four">
          <SummaryCard label="Total manifests" value={plans.length} note="Limit: 25 most recent records" />
          <SummaryCard label="States" value={summary.stateSummary} note="Count by manifest state" />
          <SummaryCard
            label="Execution submitted"
            value={formatBool(summary.executionSubmitted)}
            note="True means a stored manifest says execution was submitted elsewhere"
          />
          <SummaryCard
            label="Outputs hashed"
            value={summary.outputShaCount}
            note={`Latest created: ${formatDate(summary.latestCreatedAt)}`}
          />
        </div>
      </Section>

      {loadState === 'loading' ? (
        <Empty title="Loading manifests" detail="Reading existing plan manifests from the GET-only list endpoint." />
      ) : null}

      {loadState === 'error' && error ? <ErrorNotice message={error} /> : null}

      {loadState === 'ready' && plans.length === 0 ? (
        <Empty title="No post-production manifests found" detail="The backend returned an empty manifest list." />
      ) : null}

      {plans.length ? (
        <Section title="Manifest evidence" subtitle="Each record is displayed as inert text; paths and commands are not links or controls.">
          <div className="disabled-action-grid">
            {plans.map((manifest) => (
              <ManifestCard key={manifest.plan_id} manifest={manifest} />
            ))}
          </div>
        </Section>
      ) : null}
    </div>
  )
}
