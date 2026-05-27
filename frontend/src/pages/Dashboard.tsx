import { useEffect, useState } from 'react'
import { api, type Campaign, type HealthResponse, type Job, type Project, type RootStatus } from '../api/client'
import { DebugPanel, EmptyState, ErrorNotice } from '../components/Cards'
import { PageHeader, formatDate } from '../components/Page'
import { StatusCard } from '../components/Cards'

type DashboardHealth = {
  backend: HealthResponse | null
  comfy: HealthResponse | null
  gpu: HealthResponse | null
  ffmpeg: HealthResponse | null
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
    comfy: null,
    gpu: null,
    ffmpeg: null,
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
        const [root, backend, comfy, gpu, ffmpeg, projectList, campaignList, jobList] = await Promise.all([
          api.rootStatus(),
          api.health(),
          api.comfyHealth(),
          api.gpuHealth(),
          api.ffmpegHealth(),
          api.listProjects(),
          api.listCampaigns(),
          api.listJobs(),
        ])

        if (cancelled) {
          return
        }

        setRootStatus(root)
        setHealth({ backend, comfy, gpu, ffmpeg })
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
        description="A polished local control dashboard for DB-backed planning, runtime readiness, and the intentionally gated generation path."
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
          status={statusOf(health.comfy)}
          detail="Reachability is read-only. Prompt submission remains blocked."
          meta="GET /health/comfy"
        />
        <StatusCard
          title="GPU"
          status={statusOf(health.gpu)}
          detail="GPU telemetry reports availability without failing the UI."
          meta="GET /health/gpu"
        />
        <StatusCard
          title="FFmpeg"
          status={statusOf(health.ffmpeg)}
          detail="Binary availability is checked. Assembly is disabled."
          meta="GET /health/ffmpeg"
        />
        <StatusCard
          title="Queue"
          status="degraded"
          detail="Controlled worker submission exists; public generation remains disabled."
          meta={`${jobs.length} visible jobs`}
        />
      </section>

      <section className="panel-grid">
        <article className="panel">
          <div className="panel-title">
            <h2>Recent Activity</h2>
            <span>{loading ? 'Loading' : 'Live backend data where available'}</span>
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
            Controlled ComfyUI submission now runs only through the worker/runtime service boundary after readiness
            checks. Public UI generation, WebSockets, outputs, and autonomy remain disabled.
          </p>
          <DebugPanel title="Backend status snapshot" data={{ rootStatus, health }} />
        </article>
      </section>
    </div>
  )
}
