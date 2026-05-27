import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, type Job } from '../api/client'
import { DebugPanel, EmptyState, ErrorNotice, SuccessNotice } from '../components/Cards'
import { PageHeader } from '../components/Page'
import { StatusBadge } from '../components/StatusBadge'

export function Jobs() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [jobId, setJobId] = useState('')
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function loadJobs() {
    setLoading(true)
    setError(null)
    try {
      setJobs(await api.listJobs())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load jobs.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadJobs()
  }, [])

  async function readJob(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setMessage(null)
    try {
      const job = await api.getJob(jobId.trim())
      setSelectedJob(job)
      setMessage(`Loaded job ${job.id}.`)
    } catch (err) {
      setSelectedJob(null)
      setError(err instanceof Error ? err.message : 'Unable to read job.')
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Jobs"
        title="Generation job read path"
        description="Inspect persisted job state without creating or submitting any generation work."
      />

      {error ? <ErrorNotice message={error} /> : null}
      {message ? <SuccessNotice message={message} /> : null}

      <section className="form-grid single">
        <form className="panel form-panel" onSubmit={readJob}>
          <h2>Read Job By ID</h2>
          <label>
            Job ID
            <input value={jobId} onChange={(event) => setJobId(event.target.value)} placeholder="UUID" />
          </label>
          <button className="secondary-button" type="submit">
            Load job status
          </button>
          {selectedJob ? <DebugPanel title="Selected job response" data={selectedJob} /> : null}
        </form>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Jobs</h2>
          <span>{loading ? 'Loading...' : `${jobs.length} visible`}</span>
        </div>
        {jobs.length === 0 ? (
          <EmptyState
            title="No generation jobs yet."
            detail="Job creation begins after controlled submission is enabled."
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Workflow Run</th>
                  <th>Comfy Prompt</th>
                  <th>Error</th>
                  <th>ID</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td>
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="mono">{job.workflow_run_id ?? 'None'}</td>
                    <td>{job.comfy_prompt_id ?? 'Not submitted'}</td>
                    <td>{job.error_message ?? 'None'}</td>
                    <td className="mono">{job.id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
