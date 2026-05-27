import { useEffect, useState } from 'react'
import { api, type Job, type RuntimeStatus } from '../api/client'
import { EmptyState, ErrorNotice } from '../components/Cards'
import { PageHeader } from '../components/Page'
import { StatusBadge } from '../components/StatusBadge'

export function Queue() {
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadQueueSurface() {
      setLoading(true)
      setError(null)
      try {
        const [runtimeStatus, jobList] = await Promise.all([api.runtimeStatus(), api.listJobs()])
        if (!cancelled) {
          setRuntime(runtimeStatus)
          setJobs(jobList)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unable to load queue status.')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadQueueSurface()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="page">
      <PageHeader
        eyebrow="Queue"
        title="Queue foundation"
        description="A real read-only queue surface for the current backend foundation. Controlled worker submission exists, but public queue mutation and user-facing generation remain unavailable."
      />

      {error ? <ErrorNotice message={error} /> : null}

      <section className="grid three">
        <article className="card">
          <div className="card-heading">
            <span>Queue Worker</span>
            <StatusBadge status={runtime?.queue.worker_enabled ? 'enabled' : 'disabled'} />
          </div>
          <p>Worker foundation exists. Local worker execution is controlled by backend configuration.</p>
        </article>
        <article className="card">
          <div className="card-heading">
            <span>Controlled Submission</span>
            <StatusBadge status={runtime?.queue.controlled_submission_enabled ? 'ok' : 'disabled'} />
          </div>
          <p>Worker/runtime context can submit only after readiness passes. No public Generate control is exposed.</p>
        </article>
        <article className="card">
          <div className="card-heading">
            <span>Queue API</span>
            <StatusBadge status="degraded" label="read-only" />
          </div>
          <p>Backend queue UI remains read-only while worker telemetry and public controls stay gated.</p>
        </article>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Supported States</h2>
          <span>{loading ? 'Loading...' : `${runtime?.queue.supported_states.length ?? 0} states`}</span>
        </div>
        <div className="state-list">
          {(runtime?.queue.supported_states ?? []).map((state) => (
            <StatusBadge key={state} status={state} />
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Visible Jobs</h2>
          <span>Read-only</span>
        </div>
        {jobs.length === 0 ? (
          <EmptyState
            title="No queued jobs visible."
            detail="Generation jobs will appear here after controlled submission is enabled."
          />
        ) : (
          <div className="activity-list">
            {jobs.map((job) => (
              <div key={job.id}>
                <strong>{job.status}</strong>
                <span className="mono">{job.id}</span>
                <small>{job.detail}</small>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
