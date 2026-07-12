import { useState } from 'react'
import { useStudio } from '../StudioContext'
import { countScenes, countShots, formatDuration } from '../utils'

export function OverviewPage() {
  const { data, readiness, approvePlan, busy, backendStatus } = useStudio()
  const [approver, setApprover] = useState('Producer')

  if (!data) return null

  const metrics: Array<[string, string | number]> = [
    ['Chapters', data.chapters.length],
    ['Scenes', countScenes(data.chapters)],
    ['Shots', countShots(data.chapters)],
    ['Characters', data.characters.length],
    ['Voice profiles', data.voices.length],
    ['Readiness', readiness ? (readiness.ready ? 'Ready' : 'Review') : 'Unknown'],
  ]

  const planned = readiness?.planned_duration_sec ?? 0
  const target = readiness?.target_duration_sec ?? data.story.target_duration_sec
  const ratio = target > 0 ? Math.min(100, Math.round((planned / target) * 100)) : 0
  const blocking = readiness?.reasons.filter((reason) => reason.blocking) ?? []
  const canApprove = Boolean(readiness?.ready) && !busy

  return (
    <>
      <div className="studio-metrics" aria-label="Planning metrics">
        {metrics.map(([label, value]) => (
          <article key={String(label)}>
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </div>

      <div className="split-2">
        <div className="panel">
          <div className="panel-title">
            <div>
              <h2>Duration alignment</h2>
              <p>Values come from the readiness endpoint, not client estimates.</p>
            </div>
            <span className="truth-pill">{backendStatus}</span>
          </div>
          <ul className="kv-list">
            <li>
              <span>Planned</span>
              <strong>{formatDuration(planned)}</strong>
            </li>
            <li>
              <span>Target</span>
              <strong>{formatDuration(target)}</strong>
            </li>
            <li>
              <span>Discrepancy</span>
              <strong>
                {readiness ? `${readiness.discrepancy_sec >= 0 ? '+' : ''}${readiness.discrepancy_sec}s` : '—'}
              </strong>
            </li>
            <li>
              <span>Approval state</span>
              <strong>{data.story.approval_state}</strong>
            </li>
          </ul>
          <div className="progress-bar" aria-hidden="true">
            <span style={{ width: `${ratio}%` }} />
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">
            <div>
              <h2>Safety posture</h2>
              <p>Approval creates an immutable storyboard version only.</p>
            </div>
          </div>
          <ul className="feature-list">
            <li>No Timeline Slot</li>
            <li>No Clip Iteration</li>
            <li>No queue job</li>
            <li>No ComfyUI submission</li>
            <li>No FFmpeg job</li>
            <li>No voice clone / TTS batch</li>
          </ul>
        </div>
      </div>

      <div className="panel">
        <div className="panel-title">
          <div>
            <h2>Backend readiness gates</h2>
            <p>
              Gate truth is returned by <span className="mono">/storyboard/stories/:id/readiness</span>.
              The UI never hard-codes ready/not-ready.
            </p>
          </div>
          <span className={`truth-pill ${readiness?.ready ? 'verified' : 'unknown'}`}>
            {readiness ? (readiness.ready ? 'Server: ready' : 'Server: not ready') : 'Server: unknown'}
          </span>
        </div>

        <ul className="gate-list">
          {readiness?.reasons?.length ? (
            readiness.reasons.map((reason) => (
              <li key={`${reason.code}-${reason.entity_id ?? 'none'}-${reason.message}`}>
                <b>{reason.code}</b>
                <span>{reason.message}</span>
                <span className={reason.blocking ? 'gate-blocking' : 'gate-info'}>
                  {reason.blocking ? 'Blocking' : 'Info'}
                </span>
              </li>
            ))
          ) : readiness?.ready ? (
            <li>
              <b>ready</b>
              <span>All current backend readiness checks pass.</span>
              <span className="gate-info">Pass</span>
            </li>
          ) : (
            <li>
              <b>pending</b>
              <span>Readiness reasons have not been returned yet.</span>
              <span className="gate-blocking">Unknown</span>
            </li>
          )}
        </ul>

        <div className="stack-form" style={{ maxWidth: 420 }}>
          <label>
            Approved by
            <input
              value={approver}
              onChange={(event) => setApprover(event.target.value)}
              disabled={busy}
              autoComplete="name"
            />
          </label>
          <button
            type="button"
            className="primary-button touch-target"
            disabled={!canApprove || !approver.trim()}
            title={
              readiness?.ready
                ? 'Approve production plan on the server'
                : blocking.length
                  ? `Blocked by ${blocking.length} readiness gate(s)`
                  : 'Server has not marked this plan ready'
            }
            onClick={() => void approvePlan(approver.trim())}
          >
            Approve production plan
          </button>
          {!readiness?.ready ? (
            <p className="form-hint">
              Approve stays disabled until the backend reports <code>ready: true</code>.
            </p>
          ) : null}
        </div>
      </div>
    </>
  )
}
