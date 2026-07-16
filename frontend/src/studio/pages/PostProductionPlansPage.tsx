import { useEffect, useMemo, useState } from 'react'
import { api, type PostProductionPlanManifest, type PostProductionRecipeCommandManifest } from '../../api/client'
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

type JsonRecord = Record<string, unknown>

function isJsonRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function safeProbeToken(value: unknown): string | null {
  if (typeof value !== 'string') return null
  if (value.length > 40) return null
  if (!/^[a-z0-9][a-z0-9_.+-]*$/i.test(value)) return null
  return value
}

function summarizeKeys(record: JsonRecord | null | undefined): string {
  if (!record) return 'none'
  const keys = Object.keys(record)
    .filter((key) => !/(filename|filepath|path|url|uri|tag|metadata)/i.test(key))
    .sort()
  if (!keys.length) return 'none'
  const visibleKeys = keys.slice(0, 8).join(', ')
  return keys.length > 8 ? `${visibleKeys}, +${keys.length - 8} more` : visibleKeys
}

function probeJsonRecordSummary(probeJson: JsonRecord, index: number): string {
  const streams = Array.isArray(probeJson.streams) ? probeJson.streams.filter(isJsonRecord) : []
  const codecTypes = Array.from(new Set(streams.map((stream) => safeProbeToken(stream.codec_type)).filter(Boolean)))
  const codecNames = Array.from(new Set(streams.map((stream) => safeProbeToken(stream.codec_name)).filter(Boolean)))
  const format = isJsonRecord(probeJson.format) ? probeJson.format : null

  return [
    `${String(index).padStart(2, '0')}: top-level keys=${summarizeKeys(probeJson)}`,
    `streams=${formatNumber(streams.length)}`,
    `codec types=${codecTypes.length ? codecTypes.slice(0, 4).join(', ') : 'none'}`,
    `codec names=${codecNames.length ? codecNames.slice(0, 4).join(', ') : 'none'}`,
    `format keys=${summarizeKeys(format)}`,
  ].join('; ')
}

function probeJsonSummary(options: {
  records: JsonRecord[]
  emptyMessage: string
  countLabel: string
  declaredCount?: number
  declaredCountLabel?: string
  maxRecords?: number
}): string {
  const { records, emptyMessage, countLabel, declaredCount, declaredCountLabel, maxRecords = 5 } = options

  if ((declaredCount ?? 0) === 0 && records.length === 0) {
    return emptyMessage
  }

  const lines = declaredCountLabel ? [`${declaredCountLabel}: ${formatNumber(declaredCount)}`] : []
  lines.push(`${countLabel}: ${formatNumber(records.length)}`)

  if (typeof declaredCount === 'number' && declaredCount !== records.length) {
    lines.push('Note: persisted count differs from summarized JSON record count.')
  }

  records.slice(0, maxRecords).forEach((probeJson, index) => {
    lines.push(probeJsonRecordSummary(probeJson, index))
  })

  if (records.length > maxRecords) {
    lines.push(`+${formatNumber(records.length - maxRecords)} additional probe JSON record(s) not expanded.`)
  }

  return lines.join('\n')
}

function inputProbeSummary(manifest: PostProductionRecipeCommandManifest): string {
  const declaredCount = typeof manifest.input_probe_count === 'number' ? manifest.input_probe_count : 0
  const probeJsons = Array.isArray(manifest.input_probe_jsons) ? manifest.input_probe_jsons.filter(isJsonRecord) : []

  return probeJsonSummary({
    records: probeJsons,
    emptyMessage: 'No input probe JSON provenance persisted for this recipe command.',
    countLabel: 'Persisted input_probe_json records summarized',
    declaredCount,
    declaredCountLabel: 'Persisted input_probe_count',
  })
}

function finalProbeSummary(finalProbeJson: Record<string, unknown> | null): string {
  const probeJsons = isJsonRecord(finalProbeJson) ? [finalProbeJson] : []

  return probeJsonSummary({
    records: probeJsons,
    emptyMessage: 'No final_probe_json persisted for this manifest.',
    countLabel: 'Persisted final_probe_json records summarized',
    maxRecords: 1,
  })
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

      {manifest.final_probe_json ? (
        <div className="debug-panel" aria-label="Read-only final probe summary">
          <span className="eyebrow">FINAL PROBE JSON · SAFE SUMMARY ONLY</span>
          <pre>
            <code>{finalProbeSummary(manifest.final_probe_json)}</code>
          </pre>
        </div>
      ) : null}

      <div className="debug-panel" aria-label="Read-only command preview">
        <span className="eyebrow">COMMAND PREVIEW · INERT ARGV TEXT</span>
        <pre>
          <code>{commandPreview(manifest.command)}</code>
        </pre>
      </div>
    </article>
  )
}

function RecipeCommandCard({ manifest }: { manifest: PostProductionRecipeCommandManifest }) {
  return (
    <article className="panel">
      <header className="panel-head">
        <div>
          <h2 className="mono">{manifest.plan_id}</h2>
          <p>Read-only generic FFmpeg recipe command manifest evidence.</p>
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
        <EvidenceRow label="Manifest path" value={manifest.manifest_path || '—'} mono />
        <EvidenceRow label="Output path" value={manifest.output_path || '—'} mono />
        <EvidenceRow label="Input paths" value={manifest.input_paths.length} />
        <EvidenceRow label="Input hashes" value={manifest.input_hashes.length} />
        <EvidenceRow label="Input probe count" value={formatNumber(manifest.input_probe_count)} />
        <EvidenceRow
          label="Input probe JSON records"
          value={Array.isArray(manifest.input_probe_jsons) ? manifest.input_probe_jsons.length : 0}
        />
        <EvidenceRow label="Output SHA-256" value={manifest.output_sha256 || '—'} mono />
        <EvidenceRow label="Recorded error" value={manifest.error || '—'} />
      </div>

      <div className="debug-panel" aria-label="Read-only input probe provenance summary">
        <span className="eyebrow">INPUT PROBE PROVENANCE · SAFE SUMMARY ONLY</span>
        <pre>
          <code>{inputProbeSummary(manifest)}</code>
        </pre>
      </div>

      {manifest.final_probe_json ? (
        <div className="debug-panel" aria-label="Read-only recipe command final probe summary">
          <span className="eyebrow">FINAL PROBE JSON · SAFE SUMMARY ONLY</span>
          <pre>
            <code>{finalProbeSummary(manifest.final_probe_json)}</code>
          </pre>
        </div>
      ) : null}

      <div className="debug-panel" aria-label="Read-only recipe command argv display">
        <span className="eyebrow">RECIPE COMMAND ARGV · INERT TEXT ONLY</span>
        <pre>
          <code>{commandPreview(manifest.command)}</code>
        </pre>
      </div>
    </article>
  )
}

export function PostProductionPlansPage() {
  const [plans, setPlans] = useState<PostProductionPlanManifest[]>([])
  const [recipeCommands, setRecipeCommands] = useState<PostProductionRecipeCommandManifest[]>([])
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true

    Promise.all([api.listPostProductionPlans(25), api.listPostProductionRecipeCommands(25)])
      .then(([planManifests, recipeCommandManifests]) => {
        if (!mounted) return
        setPlans(planManifests)
        setRecipeCommands(recipeCommandManifests)
        setError(null)
        setLoadState('ready')
      })
      .catch((caught: unknown) => {
        if (!mounted) return
        setPlans([])
        setRecipeCommands([])
        setError(caught instanceof Error ? caught.message : 'Unable to load post-production manifests.')
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
    const latestRecipeCreatedAt = recipeCommands
      .map((manifest) => manifest.created_at)
      .filter(Boolean)
      .sort((a, b) => Date.parse(b) - Date.parse(a))[0]

    return {
      stateSummary: stateSummary || 'No states recorded',
      executionSubmitted: plans.some((plan) => plan.execution_submitted),
      outputShaCount: plans.filter((plan) => Boolean(plan.output_sha256)).length,
      latestCreatedAt: latestCreatedAt ?? null,
      recipeCommandCount: recipeCommands.length,
      recipeCommandTemplates: new Set(recipeCommands.map((manifest) => manifest.command_template_id)).size,
      recipeExecutionSubmitted: recipeCommands.some((manifest) => manifest.execution_submitted),
      latestRecipeCreatedAt: latestRecipeCreatedAt ?? null,
    }
  }, [plans, recipeCommands])

  return (
    <div className="studio-page">
      <PageTitle
        eyebrow="OFFLINE POST-PRODUCTION"
        title="Plan and recipe command manifests"
        description="Read-only evidence from GET /local-post-production/plans and GET /local-post-production/recipe-commands. This page does not create plans, execute FFmpeg, submit jobs, render media, or call ComfyUI/GPU."
      />

      <section className="safety-banner" aria-label="Post-production safety boundary">
        <div>
          <strong>Read-only checkpoint</strong>
          <p>
            Existing local manifests are displayed as inert text only. No command input, copy, run, execution endpoint,
            benchmark, render, download, submission, ComfyUI, or GPU action is exposed here.
          </p>
        </div>
        <StatusPill status="GET only" />
      </section>

      <Section title="Manifest summary" subtitle="Recent offline post-production evidence from backend GET list endpoints.">
        <div className="grid four">
          <SummaryCard label="Plan manifests" value={plans.length} note="Limit: 25 most recent plan records" />
          <SummaryCard label="Plan states" value={summary.stateSummary} note="Count by plan manifest state" />
          <SummaryCard
            label="Recipe command manifests"
            value={summary.recipeCommandCount}
            note={`${summary.recipeCommandTemplates} template id(s); latest: ${formatDate(summary.latestRecipeCreatedAt)}`}
          />
          <SummaryCard
            label="Execution submitted"
            value={formatBool(summary.executionSubmitted || summary.recipeExecutionSubmitted)}
            note="True means stored evidence says execution was submitted elsewhere"
          />
          <SummaryCard
            label="Plan outputs hashed"
            value={summary.outputShaCount}
            note={`Latest plan created: ${formatDate(summary.latestCreatedAt)}`}
          />
        </div>
      </Section>

      {loadState === 'loading' ? (
        <Empty title="Loading manifests" detail="Reading existing manifests from GET-only list endpoints." />
      ) : null}

      {loadState === 'error' && error ? <ErrorNotice message={error} /> : null}

      {loadState === 'ready' && plans.length === 0 && recipeCommands.length === 0 ? (
        <Empty title="No post-production manifests found" detail="The backend returned empty manifest lists." />
      ) : null}

      {plans.length ? (
        <Section title="Plan manifest evidence" subtitle="Each record is displayed as inert text; paths and commands are not links or controls.">
          <div className="disabled-action-grid">
            {plans.map((manifest) => (
              <ManifestCard key={manifest.plan_id} manifest={manifest} />
            ))}
          </div>
        </Section>
      ) : null}

      {recipeCommands.length ? (
        <Section
          title="Recipe command manifest evidence"
          subtitle="Read-only generic FFmpeg recipe command records from GET /local-post-production/recipe-commands; argv is displayed as inert text only."
        >
          <div className="disabled-action-grid">
            {recipeCommands.map((manifest) => (
              <RecipeCommandCard key={manifest.plan_id} manifest={manifest} />
            ))}
          </div>
        </Section>
      ) : null}
    </div>
  )
}
