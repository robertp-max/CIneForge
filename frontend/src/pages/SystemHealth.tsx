import { useEffect, useState } from 'react'
import { api, type HealthResponse } from '../api/client'
import { DebugPanel, ErrorNotice } from '../components/Cards'
import { PageHeader } from '../components/Page'
import { StatusCard } from '../components/Cards'

type HealthState = {
  backend: HealthResponse | null
  comfy: HealthResponse | null
  gpu: HealthResponse | null
  ffmpeg: HealthResponse | null
}

function statusOf(response: HealthResponse | null): string {
  return response?.status ? String(response.status) : 'unavailable'
}

export function SystemHealth() {
  const [health, setHealth] = useState<HealthState>({
    backend: null,
    comfy: null,
    gpu: null,
    ffmpeg: null,
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadHealth() {
      setLoading(true)
      setError(null)
      try {
        const [backend, comfy, gpu, ffmpeg] = await Promise.all([
          api.health(),
          api.comfyHealth(),
          api.gpuHealth(),
          api.ffmpegHealth(),
        ])
        if (!cancelled) {
          setHealth({ backend, comfy, gpu, ffmpeg })
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
        title="Read-only runtime checks"
        description="Health cards call the FastAPI health endpoints and degrade gracefully when services are offline."
      />

      {error ? <ErrorNotice message={error} /> : null}

      <section className="grid four">
        <StatusCard
          title="Backend"
          status={statusOf(health.backend)}
          detail={loading ? 'Checking...' : 'Application health and runtime flags.'}
          meta="GET /health"
        />
        <StatusCard
          title="ComfyUI"
          status={statusOf(health.comfy)}
          detail="External ComfyUI reachability only; no prompt submission."
          meta="GET /health/comfy"
        />
        <StatusCard
          title="GPU"
          status={statusOf(health.gpu)}
          detail="nvidia-smi based telemetry status."
          meta="GET /health/gpu"
        />
        <StatusCard
          title="FFmpeg"
          status={statusOf(health.ffmpeg)}
          detail="ffmpeg and ffprobe binary availability."
          meta="GET /health/ffmpeg"
        />
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Raw Status Summary</h2>
          <span>Optional debug response</span>
        </div>
        <DebugPanel title="Health payloads" data={health} />
      </section>
    </div>
  )
}
