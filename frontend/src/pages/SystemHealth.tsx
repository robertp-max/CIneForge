import { useEffect, useState } from 'react'
import { api, type HealthResponse, type RootStatus } from '../api/client'
import { DebugPanel, ErrorNotice } from '../components/Cards'
import { PageHeader } from '../components/Page'
import { StatusCard } from '../components/Cards'

type HealthState = {
  root: RootStatus | null
  backend: HealthResponse | null
}

function statusOf(response: HealthResponse | null): string {
  return response?.status ? String(response.status) : 'unavailable'
}

export function SystemHealth() {
  const [health, setHealth] = useState<HealthState>({
    root: null,
    backend: null,
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadHealth() {
      setLoading(true)
      setError(null)
      try {
        const [root, backend] = await Promise.all([api.rootStatus(), api.health()])
        if (!cancelled) {
          setHealth({ root, backend })
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unable to load health endpoints.')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadHealth()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="page">
      <PageHeader
        eyebrow="System Health"
        title="Read-only backend checks"
        description="This page reads only backend/root metadata automatically. Live ComfyUI, GPU, and FFmpeg probes require explicit external approval and are not auto-run."
      />

      {error ? <ErrorNotice message={error} /> : null}

      <section className="grid four">
        <StatusCard
          title="Root Status"
          status={health.root?.status ?? 'unavailable'}
          detail={health.root?.message ?? 'Backend root status endpoint.'}
          meta="GET /"
        />
        <StatusCard
          title="Backend"
          status={statusOf(health.backend)}
          detail={loading ? 'Checking...' : 'Application health and runtime flags.'}
          meta="GET /health"
        />
        <StatusCard
          title="ComfyUI"
          status="not probed"
          detail="External ComfyUI reachability is not automatically checked from this UI. Approval is required before any live runtime probe."
          meta="Live /health/comfy probe disabled in UI"
        />
        <StatusCard
          title="GPU"
          status="not probed"
          detail="GPU telemetry is not automatically checked from this UI. Hardware readiness is not claimed."
          meta="Live /health/gpu probe disabled in UI"
        />
        <StatusCard
          title="FFmpeg"
          status="not probed"
          detail="ffmpeg and ffprobe availability are not automatically checked from this UI."
          meta="Live /health/ffmpeg probe disabled in UI"
        />
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Raw Status Summary</h2>
          <span>Backend/root only</span>
        </div>
        <DebugPanel
          title="Health payloads"
          data={{ ...health, externalRuntimeProbes: 'not auto-probed; approval required' }}
        />
      </section>
    </div>
  )
}
