import { useEffect, useState } from 'react'
import { api, type Job } from '../api/client'
import { EmptyState, ErrorNotice } from '../components/Cards'
import { PageHeader } from '../components/Page'
import { StatusBadge } from '../components/StatusBadge'

export function Queue() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadQueueSurface() {
      setLoading(true)
      setError(null)
      try {
        const jobList = await api.listJobs()
        if (!cancelled) {
          setJobs(jobList)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unable to load queue jobs.')
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
        description="A read-only queue surface for backend job metadata. Runtime worker status is not auto-probed, and public queue mutation and user-facing generation remain unavailable."
      />

      {error ? <ErrorNotice message={error} /> : null}

      <section className="grid three">
        <article className="card">
          <div className="card-heading">
            <span>Queue Worker</span>
            <StatusBadge status="disabled" label="not auto-probed" />
          </div>
          <p>Worker enablement is runtime metadata and is not automatically checked by this UI.</p>
        </article>
        <article className="card">
          <div className="card-heading">
            <span>Controlled Submission</span>
            <StatusBadge status="disabled" label="approval required" />
          </div>
          <p>Submission capability requires explicit approval and is not inferred from a live runtime probe.</p>
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
          <h2>Runtime Metadata</h2>
          <span>not auto-probed</span>
        </div>
        <EmptyState
          title="Runtime status not loaded."
          detail="Supported states, worker enablement, and controlled-submission flags are live runtime metadata. This UI does not call the runtime status probe automatically."
        />
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Visible Jobs</h2>
          <span>{loading ? 'Loading jobs...' : 'Read-only'}</span>
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
