import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, type Job, type LocalJobManifest } from '../api/client'
import { DebugPanel, EmptyState, ErrorNotice, SuccessNotice } from '../components/Cards'
import { PageHeader } from '../components/Page'
import { StatusBadge } from '../components/StatusBadge'

export function Jobs() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [localJobs, setLocalJobs] = useState<LocalJobManifest[]>([])
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [jobId, setJobId] = useState('')
  const [projectKey, setProjectKey] = useState('local-project')
  const [runStem, setRunStem] = useState('run-001')
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function loadJobs() {
    setLoading(true)
    setError(null)
    try {
      const [jobList, localJobList] = await Promise.all([api.listJobs(), api.listLocalJobs()])
      setJobs(jobList)
      setLocalJobs(localJobList)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load jobs.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => void loadJobs(), 0)
    return () => window.clearTimeout(timer)
  }, [])

  async function createLocalManifest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setMessage(null)
    try {
      const manifest = await api.createLocalJob({
        project_key: projectKey.trim(),
        run_stem: runStem.trim(),
        prompt,
      })
      setMessage(`Prepared local manifest ${manifest.job_id}. No ComfyUI prompt was submitted.`)
      setLocalJobs(await api.listLocalJobs())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to prepare local manifest.')
    }
  }

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

      <section className="form-grid two">
        <form className="panel form-panel" onSubmit={createLocalManifest}>
          <h2>Prepare Local Manifest</h2>
          <p>
            Creates a file-backed manifest, project output folder, and offline workflow snapshot only. It does not
            submit to ComfyUI.
          </p>
          <label>
            Project folder key
            <input value={projectKey} onChange={(event) => setProjectKey(event.target.value)} />
          </label>
          <label>
            Run stem
            <input value={runStem} onChange={(event) => setRunStem(event.target.value)} />
          </label>
          <label>
            Prompt
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={4} />
          </label>
          <button className="primary-button" type="submit">
            Prepare manifest only
          </button>
        </form>

        <form className="panel form-panel" onSubmit={readJob}>
          <h2>Read DB Job By ID</h2>
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
          <h2>Local File-backed Manifests</h2>
          <span>{loading ? 'Loading...' : `${localJobs.length} visible`}</span>
        </div>
        {localJobs.length === 0 ? (
          <EmptyState
            title="No local manifests yet."
            detail="Use Prepare Local Manifest to create a DB-free record without generation."
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>State</th>
                  <th>Prefix</th>
                  <th>Preset</th>
                  <th>Template</th>
                  <th>Generation</th>
                  <th>ID</th>
                </tr>
              </thead>
              <tbody>
                {localJobs.map((job) => (
                  <tr key={job.job_id}>
                    <td>
                      <StatusBadge status={job.state} />
                    </td>
                    <td className="mono">{job.filename_prefix}</td>
                    <td>{job.preset_id}</td>
                    <td>{job.workflow_template_id ?? 'None'}</td>
                    <td>{job.generation_submitted ? 'Submitted' : 'Not submitted'}</td>
                    <td className="mono">{job.job_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>DB Jobs</h2>
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
