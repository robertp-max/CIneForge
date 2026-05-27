import { useEffect, useState } from 'react'
import { api, type RuntimeStatus } from '../api/client'
import { DebugPanel, ErrorNotice } from '../components/Cards'
import { PageHeader } from '../components/Page'
import { StatusCard } from '../components/Cards'
import { StatusBadge } from '../components/StatusBadge'

const disabledActions = [
  ['Submit prompt', 'Controlled /prompt submission begins in Phase 2.'],
  ['WebSocket monitor', 'Progress streams open after prompt submission is controlled.'],
  ['Output collection', 'History and output reads remain blocked in this slice.'],
  ['FFmpeg assembly', 'Assembly is planned after output collection and validation exist.'],
]

export function Runtime() {
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadRuntime() {
      setLoading(true)
      setError(null)
      try {
        const status = await api.runtimeStatus()
        if (!cancelled) {
          setRuntime(status)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unable to load runtime status.')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadRuntime()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="page">
      <PageHeader
        eyebrow="Runtime"
        title="ComfyUI readiness boundary"
        description="Runtime status is read-only. The UI shows availability without opening prompt, WebSocket, history, output, or FFmpeg execution paths."
      />

      {error ? <ErrorNotice message={error} /> : null}

      <section className="grid three">
        <StatusCard
          title="ComfyUI Reachability"
          status={String(runtime?.comfyui.status ?? 'unavailable')}
          detail={loading ? 'Checking...' : 'Health probe against the external ComfyUI HTTP root.'}
          meta="GET /health/comfy via /runtime/status"
        />
        <StatusCard
          title="object_info"
          status={runtime?.object_info.status ?? 'unavailable'}
          detail={
            runtime?.object_info.available
              ? `${runtime.object_info.class_count ?? 0} classes visible.`
              : 'Not exposed yet or ComfyUI is unavailable.'
          }
          meta="Read-only availability probe"
        />
        <StatusCard
          title="Runtime Boundary"
          status="disabled"
          detail="Mutation routes remain blocked until the controlled submission phase."
          meta="No /prompt calls"
        />
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Disabled Runtime Actions</h2>
          <span>Intentional gates</span>
        </div>
        <div className="disabled-action-grid">
          {disabledActions.map(([title, detail]) => (
            <article key={title} className="disabled-action">
              <div>
                <strong>{title}</strong>
                <p>{detail}</p>
              </div>
              <StatusBadge status="disabled" />
            </article>
          ))}
        </div>
      </section>

      {runtime ? <DebugPanel title="Runtime status response" data={runtime} /> : null}
    </div>
  )
}
