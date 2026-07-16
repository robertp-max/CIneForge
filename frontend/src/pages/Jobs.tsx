import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, type Job, type LocalJobManifest, type SemanticGenerationRequestManifest } from '../api/client'
import { DebugPanel, EmptyState, ErrorNotice, SuccessNotice } from '../components/Cards'
import { formatDate } from '../components/formatDate'
import { PageHeader } from '../components/Page'
import { StatusBadge } from '../components/StatusBadge'

const SEMANTIC_REQUEST_DEFAULTS = {
  presetId: 'CF-PRESET-001',
  archetypeId: 'CF-VID-01',
  qualityProfile: 'draft',
  mode: 't2v' as const,
  width: 512,
  height: 288,
  frameCount: 17,
  fps: 24,
  targetDurationSec: 1,
}

export function Jobs() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [localJobs, setLocalJobs] = useState<LocalJobManifest[]>([])
  const [semanticManifests, setSemanticManifests] = useState<SemanticGenerationRequestManifest[]>([])
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [jobId, setJobId] = useState('')
  const [projectKey, setProjectKey] = useState('local-project')
  const [runStem, setRunStem] = useState('run-001')
  const [prompt, setPrompt] = useState('')
  const [semanticOutputPrefix, setSemanticOutputPrefix] = useState('M7 Project/shot 001')
  const [semanticPrompt, setSemanticPrompt] = useState('Safe offline semantic generation request.')
  const [semanticNegativePrompt, setSemanticNegativePrompt] = useState('bad quality')
  const [semanticNoExecutionAcknowledged, setSemanticNoExecutionAcknowledged] = useState(false)
  const [localManifestNoExecutionAcknowledged, setLocalManifestNoExecutionAcknowledged] = useState(false)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function loadJobs() {
    setLoading(true)
    setError(null)
    try {
      const [jobList, localJobList, semanticManifestList] = await Promise.all([
        api.listJobs(),
        api.listLocalJobs(),
        api.listSemanticGenerationRequestManifests(),
      ])
      setJobs(jobList)
      setLocalJobs(localJobList)
      setSemanticManifests(semanticManifestList)
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
    if (!localManifestNoExecutionAcknowledged) {
      setError('Acknowledge that this only prepares an offline local manifest before continuing.')
      return
    }
    try {
      const manifest = await api.createLocalJob({
        project_key: projectKey.trim(),
        run_stem: runStem.trim(),
        prompt,
      })
      setMessage(`Prepared local manifest ${manifest.job_id}. No ComfyUI prompt was submitted.`)
      setLocalManifestNoExecutionAcknowledged(false)
      setLocalJobs(await api.listLocalJobs())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to prepare local manifest.')
    }
  }

  async function createSemanticManifest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setMessage(null)
    if (!semanticNoExecutionAcknowledged) {
      setError('Acknowledge that this only prepares an offline semantic manifest before continuing.')
      return
    }
    try {
      const manifest = await api.createSemanticGenerationRequestManifest({
        preset_id: SEMANTIC_REQUEST_DEFAULTS.presetId,
        archetype_id: SEMANTIC_REQUEST_DEFAULTS.archetypeId,
        quality_profile: SEMANTIC_REQUEST_DEFAULTS.qualityProfile,
        mode: SEMANTIC_REQUEST_DEFAULTS.mode,
        prompt: semanticPrompt,
        negative_prompt: semanticNegativePrompt,
        seed: 7,
        aspect_ratio: '16:9',
        width: SEMANTIC_REQUEST_DEFAULTS.width,
        height: SEMANTIC_REQUEST_DEFAULTS.height,
        frame_count: SEMANTIC_REQUEST_DEFAULTS.frameCount,
        fps: SEMANTIC_REQUEST_DEFAULTS.fps,
        target_duration_sec: SEMANTIC_REQUEST_DEFAULTS.targetDurationSec,
        upscale_factor: 1,
        output_profile: SEMANTIC_REQUEST_DEFAULTS.qualityProfile,
        output_prefix: semanticOutputPrefix.trim(),
        production: true,
      })
      setMessage(
        `Prepared offline semantic request manifest ${manifest.request_id}. No execution, submission, render, queue job, or ComfyUI prompt occurred.`,
      )
      setSemanticNoExecutionAcknowledged(false)
      setSemanticManifests(await api.listSemanticGenerationRequestManifests())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to prepare offline semantic request manifest.')
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
        <form className="panel form-panel" onSubmit={createSemanticManifest}>
          <h2>Prepare offline semantic request manifest</h2>
          <p>
            Persists semantic intent and production gate evidence only for {SEMANTIC_REQUEST_DEFAULTS.presetId} /{' '}
            {SEMANTIC_REQUEST_DEFAULTS.archetypeId} draft t2v. No execution, submission, render, queue job, public
            generation, raw graph upload, or ComfyUI prompt occurs.
          </p>
          <div className="metadata-grid">
            <span>Preset: {SEMANTIC_REQUEST_DEFAULTS.presetId}</span>
            <span>Archetype: {SEMANTIC_REQUEST_DEFAULTS.archetypeId}</span>
            <span>Profile: {SEMANTIC_REQUEST_DEFAULTS.qualityProfile}</span>
            <span>
              Geometry: {SEMANTIC_REQUEST_DEFAULTS.width}×{SEMANTIC_REQUEST_DEFAULTS.height},{' '}
              {SEMANTIC_REQUEST_DEFAULTS.frameCount} frames @ {SEMANTIC_REQUEST_DEFAULTS.fps} fps
            </span>
          </div>
          <label>
            Safe output prefix
            <input
              value={semanticOutputPrefix}
              onChange={(event) => setSemanticOutputPrefix(event.target.value)}
              placeholder="Project/run-stem"
            />
          </label>
          <label>
            Semantic prompt text
            <textarea value={semanticPrompt} onChange={(event) => setSemanticPrompt(event.target.value)} rows={4} />
          </label>
          <label>
            Negative prompt text
            <textarea
              value={semanticNegativePrompt}
              onChange={(event) => setSemanticNegativePrompt(event.target.value)}
              rows={2}
            />
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={semanticNoExecutionAcknowledged}
              onChange={(event) => setSemanticNoExecutionAcknowledged(event.target.checked)}
            />
            I acknowledge this prepares an offline semantic manifest only and does not execute, submit, render, create a
            queue job, acquire a GPU lease, call runtime health, or send a ComfyUI prompt.
          </label>
          <button className="primary-button" type="submit">
            Prepare offline semantic manifest only
          </button>
        </form>

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
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={localManifestNoExecutionAcknowledged}
              onChange={(event) => setLocalManifestNoExecutionAcknowledged(event.target.checked)}
            />
            I acknowledge this prepares a file-backed local manifest only and does not submit a ComfyUI prompt, create a
            live queue job, acquire a GPU lease, render, or benchmark.
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
          <h2>Offline semantic request manifests</h2>
          <span>{loading ? 'Loading...' : `${semanticManifests.length} visible`}</span>
        </div>
        <p>
          Read-only manifest records from /local-generation/semantic-requests. These records show intent and gate
          evidence only; submitted prompt, queue job, and render fields must remain empty.
        </p>
        {semanticManifests.length === 0 ? (
          <EmptyState
            title="No offline semantic manifests yet."
            detail="Use Prepare offline semantic request manifest to persist intent without execution."
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>State</th>
                  <th>Created</th>
                  <th>Prefix</th>
                  <th>Preset</th>
                  <th>Gate</th>
                  <th>Execution</th>
                  <th>ID</th>
                </tr>
              </thead>
              <tbody>
                {semanticManifests.map((manifest) => (
                  <tr key={manifest.request_id}>
                    <td>
                      <StatusBadge status={manifest.state} />
                    </td>
                    <td>{formatDate(manifest.created_at)}</td>
                    <td className="mono">{manifest.request.output_prefix}</td>
                    <td>{manifest.request.preset_id}</td>
                    <td>
                      {manifest.gate_report.allowed
                        ? 'Allowed for offline preparation'
                        : `${manifest.gate_report.blocking_reasons.length} blockers`}
                    </td>
                    <td>
                      {manifest.generation_submitted || manifest.comfy_prompt_id || manifest.queue_job_id
                        ? 'Unexpected submission marker'
                        : 'Not submitted'}
                    </td>
                    <td className="mono">{manifest.request_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
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
