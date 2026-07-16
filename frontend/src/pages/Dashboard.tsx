import { useEffect, useState } from 'react'
import { api, type Campaign, type HealthResponse, type Job, type Project, type RootStatus } from '../api/client'
import { DebugPanel, EmptyState, ErrorNotice } from '../components/Cards'
import { PageHeader } from '../components/Page'
import { formatDate } from '../components/formatDate'
import { StatusCard } from '../components/Cards'

type DashboardHealth = {
  backend: HealthResponse | null
}

type DashboardProps = {
  onBackendStatus: (status: string) => void
}

function statusOf(response: HealthResponse | null): string {
  return response?.status ? String(response.status) : 'unavailable'
}

export function Dashboard({ onBackendStatus }: DashboardProps) {
  const [health, setHealth] = useState<DashboardHealth>({
    backend: null,
  })
  const [projects, setProjects] = useState<Project[]>([])
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [rootStatus, setRootStatus] = useState<RootStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadDashboard() {
      setLoading(true)
      setError(null)
      try {
        const [root, backend, projectList, campaignList, jobList] = await Promise.all([
          api.rootStatus(),
          api.health(),
          api.listProjects(),
          api.listCampaigns(),
          api.listJobs(),
        ])

        if (cancelled) {
          return
        }

        setRootStatus(root)
        setHealth({ backend })
        setProjects(projectList)
        setCampaigns(campaignList)
        setJobs(jobList)
        onBackendStatus(statusOf(backend))
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unable to load dashboard.')
          onBackendStatus('unavailable')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadDashboard()
    return () => {
      cancelled = true
    }
  }, [onBackendStatus])

  return (
    <div className="page">
      <PageHeader
        eyebrow="CineForge"
        title="Local AI Video Orchestration MVP."
        description="A polished local control dashboard for DB-backed planning, backend health, and the intentionally gated generation path."
      />

      <section className="safety-banner">
        <div>
          <strong>Generation safety gate</strong>
          <p>User-facing generation remains disabled. Public /prompt access is not available.</p>
        </div>
        <span>{rootStatus?.current_phase ?? 'Checking current phase...'}</span>
      </section>

      {error ? <ErrorNotice message={error} /> : null}

      <section className="grid six">
        <StatusCard
          title="Backend"
          status={statusOf(health.backend)}
          detail={loading ? 'Checking FastAPI...' : rootStatus?.message ?? 'FastAPI health endpoint is connected.'}
          meta="GET / and GET /health"
        />
        <StatusCard
          title="PostgreSQL / Database"
          status={health.backend ? 'ok' : 'unavailable'}
          detail="Project, campaign, and job read paths are DB-backed."
          meta={`${projects.length} projects, ${campaigns.length} campaigns`}
        />
        <StatusCard
          title="ComfyUI"
          status="not probed"
          detail="ComfyUI reachability is not auto-probed by the dashboard. Explicit external approval is required before any live runtime check."
          meta="Live /health/comfy probe disabled in UI"
        />
        <StatusCard
          title="GPU"
          status="not probed"
          detail="GPU telemetry is not auto-probed by the dashboard. Hardware readiness is not claimed from this surface."
          meta="Live /health/gpu probe disabled in UI"
        />
        <StatusCard
          title="FFmpeg"
          status="not probed"
          detail="FFmpeg and ffprobe availability are not auto-probed by the dashboard. Assembly remains disabled."
          meta="Live /health/ffmpeg probe disabled in UI"
        />
        <StatusCard
          title="Queue"
          status="read-only"
          detail="Visible jobs come from the backend read path; runtime worker status is not auto-probed."
          meta={`${jobs.length} visible jobs`}
        />
      </section>

      <section className="panel-grid">
        <article className="panel">
          <div className="panel-title">
            <h2>Recent Activity</h2>
            <span>{loading ? 'Loading' : 'Backend read data where available'}</span>
          </div>
          {projects.length === 0 && campaigns.length === 0 && jobs.length === 0 ? (
            <EmptyState
              title="No local activity yet."
              detail="Create a project and campaign to see persisted planning activity here. Jobs appear after the controlled submission phase begins."
            />
          ) : (
            <div className="activity-list">
              {projects.slice(0, 3).map((project) => (
                <div key={project.id}>
                  <strong>Project created</strong>
                  <span>{project.name}</span>
                  <small>{formatDate(project.created_at)}</small>
                </div>
              ))}
              {campaigns.slice(0, 3).map((campaign) => (
                <div key={campaign.id}>
                  <strong>Campaign available</strong>
                  <span>{campaign.name}</span>
                  <small>{formatDate(campaign.created_at)}</small>
                </div>
              ))}
              {jobs.slice(0, 3).map((job) => (
                <div key={job.id}>
                  <strong>Job read path</strong>
                  <span>{job.status}</span>
                  <small>{job.id}</small>
                </div>
              ))}
            </div>
          )}
        </article>

        <article className="panel milestone">
          <div className="panel-title">
            <h2>Next Milestone</h2>
            <span>Phase 2</span>
          </div>
          <p>
            Controlled ComfyUI submission remains behind the worker/runtime service boundary and explicit approval.
            Public UI generation, WebSockets, outputs, live probes, and autonomy remain disabled.
          </p>
          <DebugPanel
            title="Backend status snapshot"
            data={{ rootStatus, backendHealth: health.backend, externalRuntimeProbes: 'not auto-probed' }}
          />
        </article>
      </section>
    </div>
  )
}
