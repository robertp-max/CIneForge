import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, type StorySettings } from '../../api/client'
import { useStudio } from '../StudioContext'
import { ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'

const DEFAULT_DRAFT: Omit<StorySettings, 'story_id'> = {
  duration_min_sec: 6,
  duration_max_sec: 12,
  approval_policy: 'producer_gate',
  continuity_policy: 'explicit_source_shot',
  consent_policy: 'user_provided_requires_confirmation',
  aspect_ratio: '16:9',
  render_approval_required: true,
  generation_enabled: false,
  notes: null,
}

export function SettingsPage() {
  const { data, busy, setMessage, backendStatus } = useStudio()
  const [settings, setSettings] = useState<StorySettings | null>(null)
  const [available, setAvailable] = useState(true)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState(DEFAULT_DRAFT)

  const load = useCallback(async () => {
    if (!data) return
    setLoading(true)
    setError(null)
    try {
      const result = await api.getSettings(data.story.id)
      if (result == null) {
        setAvailable(false)
        setSettings(null)
        setDraft({
          ...DEFAULT_DRAFT,
          // Reflect story target only as display context — not as invented policy truth.
          notes: `Story target duration: ${data.story.target_duration_sec}s. Settings API unavailable.`,
        })
      } else {
        setAvailable(true)
        setSettings(result)
        setDraft({
          duration_min_sec: result.duration_min_sec,
          duration_max_sec: result.duration_max_sec,
          approval_policy: result.approval_policy,
          continuity_policy: result.continuity_policy,
          consent_policy: result.consent_policy,
          aspect_ratio: result.aspect_ratio,
          render_approval_required: result.render_approval_required,
          generation_enabled: result.generation_enabled,
          notes: result.notes,
        })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings.')
    } finally {
      setLoading(false)
    }
  }, [data])

  useEffect(() => {
    void load()
  }, [load])

  if (!data) return null

  const onSave = async (event: FormEvent) => {
    event.preventDefault()
    if (!available) return
    setSaving(true)
    setError(null)
    try {
      const updated = await api.updateSettings(data.story.id, {
        ...draft,
        // Never allow the UI to silently enable generation from planning settings.
        generation_enabled: false,
        render_approval_required: true,
      })
      if (!updated) {
        setAvailable(false)
        setMessage('Settings write API is unavailable on this backend.')
        return
      }
      setSettings(updated)
      setMessage('Project settings saved on the server. Generation remains disabled in planning.')
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Could not save settings.'
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <LoadingState title="Loading project settings…" detail="Fetching server-backed policy configuration." />
  }

  if (!available) {
    return (
      <>
        <UnavailableState
          title="Settings API unavailable"
          detail="Phase 1 policy settings—duration range, approval policy, continuity, consent, aspect ratio, and render approval—are planned for persisted configuration. Runtime configuration remains read-only until the endpoint exists."
        />
        <div className="panel" style={{ marginTop: 14 }}>
          <h2>Read-only story context</h2>
          <ul className="kv-list">
            <li>
              <span>Story</span>
              <strong>{data.story.title}</strong>
            </li>
            <li>
              <span>Target duration</span>
              <strong>{data.story.target_duration_sec}s</strong>
            </li>
            <li>
              <span>Approval state</span>
              <strong>{data.story.approval_state}</strong>
            </li>
            <li>
              <span>Backend</span>
              <strong>{backendStatus}</strong>
            </li>
          </ul>
        </div>
      </>
    )
  }

  return (
    <form className="panel stack-form" style={{ maxWidth: 720 }} onSubmit={(event) => void onSave(event)}>
      <div className="panel-title">
        <div>
          <h2>Project settings</h2>
          <p>
            Persisted policy for story <span className="mono">{data.story.id}</span>. Generation cannot
            be enabled from this planning UI.
          </p>
        </div>
        <button type="button" className="ghost-button touch-target" onClick={() => void load()} disabled={busy || saving}>
          Refresh
        </button>
      </div>

      {error ? <ErrorState detail={error} onRetry={() => void load()} /> : null}

      <div className="split-2">
        <label>
          Duration min (sec)
          <input
            type="number"
            min={0}
            value={draft.duration_min_sec}
            onChange={(e) => setDraft({ ...draft, duration_min_sec: Number(e.target.value) })}
            disabled={saving}
          />
        </label>
        <label>
          Duration max (sec)
          <input
            type="number"
            min={0}
            value={draft.duration_max_sec}
            onChange={(e) => setDraft({ ...draft, duration_max_sec: Number(e.target.value) })}
            disabled={saving}
          />
        </label>
      </div>

      <label>
        Approval policy
        <select
          value={draft.approval_policy}
          onChange={(e) => setDraft({ ...draft, approval_policy: e.target.value })}
          disabled={saving}
        >
          <option value="producer_gate">Producer gate</option>
          <option value="dual_review">Dual review</option>
          <option value="auto_when_ready">Auto when ready (server-enforced)</option>
        </select>
      </label>

      <label>
        Continuity policy
        <select
          value={draft.continuity_policy}
          onChange={(e) => setDraft({ ...draft, continuity_policy: e.target.value })}
          disabled={saving}
        >
          <option value="explicit_source_shot">Explicit source shot</option>
          <option value="chapter_local">Chapter local</option>
          <option value="free">Free</option>
        </select>
      </label>

      <label>
        Consent policy
        <select
          value={draft.consent_policy}
          onChange={(e) => setDraft({ ...draft, consent_policy: e.target.value })}
          disabled={saving}
        >
          <option value="user_provided_requires_confirmation">User-provided requires confirmation</option>
          <option value="always_confirm">Always confirm</option>
          <option value="not_required_for_stock">Not required for stock</option>
        </select>
      </label>

      <label>
        Aspect ratio
        <select
          value={draft.aspect_ratio}
          onChange={(e) => setDraft({ ...draft, aspect_ratio: e.target.value })}
          disabled={saving}
        >
          <option value="16:9">16:9</option>
          <option value="9:16">9:16</option>
          <option value="1:1">1:1</option>
          <option value="2.39:1">2.39:1</option>
        </select>
      </label>

      <label style={{ gridTemplateColumns: 'auto 1fr', alignItems: 'center' }}>
        <input
          type="checkbox"
          checked={draft.render_approval_required}
          onChange={(e) => setDraft({ ...draft, render_approval_required: e.target.checked })}
          disabled={saving}
          style={{ width: 20, height: 20, minHeight: 20 }}
        />
        <span>Render approval required (recommended; forced true on save in planning)</span>
      </label>

      <label style={{ gridTemplateColumns: 'auto 1fr', alignItems: 'center' }}>
        <input
          type="checkbox"
          checked={false}
          disabled
          aria-disabled="true"
          style={{ width: 20, height: 20, minHeight: 20 }}
        />
        <span>Generation enabled — locked off in Phase 1 planning UI</span>
      </label>

      <label>
        Notes
        <textarea
          value={draft.notes ?? ''}
          onChange={(e) => setDraft({ ...draft, notes: e.target.value || null })}
          disabled={saving}
        />
      </label>

      <div className="inline-actions">
        <button type="submit" className="primary-button touch-target" disabled={saving || busy}>
          {saving ? 'Saving…' : 'Save settings'}
        </button>
        <span className="truth-pill">{settings ? 'Server-backed' : 'Unsaved'}</span>
      </div>

      <p className="form-hint">
        Runtime configuration remains observational. Saving settings never installs workflows, queues
        jobs, clones voices, or starts renders.
      </p>
    </form>
  )
}
