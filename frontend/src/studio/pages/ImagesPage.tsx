import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, type StartingImagePlan } from '../../api/client'
import { useStudio } from '../StudioContext'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'

export function ImagesPage() {
  const { data, busy, setMessage } = useStudio()
  const [items, setItems] = useState<StartingImagePlan[] | null>(null)
  const [available, setAvailable] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [label, setLabel] = useState('')
  const [purpose, setPurpose] = useState('character_reference')
  const [aspect, setAspect] = useState('16:9')
  const [notes, setNotes] = useState('')
  const [shotId, setShotId] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    if (!data) return
    setLoading(true)
    setError(null)
    try {
      const result = await api.listStartingImages(data.story.id)
      if (result == null) {
        setAvailable(false)
        setItems(null)
      } else {
        setAvailable(true)
        setItems(result)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load starting images.')
    } finally {
      setLoading(false)
    }
  }, [data])

  useEffect(() => {
    void load()
  }, [load])

  if (!data) return null

  const onCreate = async (event: FormEvent) => {
    event.preventDefault()
    if (!label.trim()) return
    setSaving(true)
    setError(null)
    try {
      const created = await api.createStartingImage(data.story.id, {
        label: label.trim(),
        purpose,
        aspect_ratio: aspect,
        notes: notes.trim() || undefined,
        shot_id: shotId.trim() || null,
      })
      if (!created) {
        setAvailable(false)
        setMessage('Starting-image write API is unavailable on this backend.')
        return
      }
      setLabel('')
      setNotes('')
      setShotId('')
      setMessage(`Starting image plan “${created.label}” saved. Generate remains disabled.`)
      await load()
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Could not create starting image plan.'
      setError(text)
      setMessage(text)
    } finally {
      setSaving(false)
    }
  }

  if (!available && !loading) {
    return (
      <UnavailableState
        title="Starting Images API unavailable"
        detail="The backend did not expose starting-image planning endpoints. Generate image remains disabled: storyboard planning never submits ComfyUI work."
      />
    )
  }

  return (
    <div className="split-2">
      <div className="panel">
        <div className="panel-title">
          <div>
            <h2>Starting image plans</h2>
            <p>
              Plan approved reference assets and starting-image requirements. Asset status comes from
              the server; this UI never claims generation completed without evidence.
            </p>
          </div>
          <button type="button" className="ghost-button touch-target" onClick={() => void load()} disabled={loading || busy}>
            Refresh
          </button>
        </div>

        {loading ? <LoadingState title="Loading starting images…" /> : null}
        {error ? <ErrorState detail={error} onRetry={() => void load()} /> : null}

        {!loading && items && !items.length ? (
          <EmptyState
            title="No starting images planned"
            detail="Create a reference plan for characters, plates, or shot kickoffs."
          />
        ) : null}

        {items && items.length ? (
          <div className="card-grid">
            {items.map((item) => (
              <article key={item.id}>
                <b>{item.label}</b>
                <small>
                  {item.purpose} · {item.aspect_ratio ?? 'aspect n/a'}
                </small>
                <p>{item.notes ?? 'No notes.'}</p>
                <ul className="kv-list">
                  <li>
                    <span>Approval</span>
                    <strong>{item.approval_state}</strong>
                  </li>
                  <li>
                    <span>Asset status</span>
                    <strong>{item.asset_status}</strong>
                  </li>
                </ul>
                <button
                  type="button"
                  className="secondary-button touch-target"
                  disabled
                  title="Generate image is disabled in planning"
                >
                  Generate image — disabled
                </button>
              </article>
            ))}
          </div>
        ) : null}
      </div>

      <form className="panel stack-form" onSubmit={(event) => void onCreate(event)}>
        <div className="panel-title">
          <div>
            <h2>Plan starting image</h2>
            <p>Server-backed planning record only.</p>
          </div>
        </div>
        <label>
          Label
          <input required value={label} onChange={(e) => setLabel(e.target.value)} disabled={saving} />
        </label>
        <label>
          Purpose
          <select value={purpose} onChange={(e) => setPurpose(e.target.value)} disabled={saving}>
            <option value="character_reference">Character reference</option>
            <option value="environment_plate">Environment plate</option>
            <option value="shot_kickoff">Shot kickoff</option>
            <option value="prop_reference">Prop reference</option>
            <option value="style_frame">Style frame</option>
          </select>
        </label>
        <label>
          Aspect ratio
          <select value={aspect} onChange={(e) => setAspect(e.target.value)} disabled={saving}>
            <option value="16:9">16:9</option>
            <option value="9:16">9:16</option>
            <option value="1:1">1:1</option>
            <option value="2.39:1">2.39:1</option>
          </select>
        </label>
        <label>
          Linked shot ID (optional)
          <input
            className="mono"
            value={shotId}
            onChange={(e) => setShotId(e.target.value)}
            disabled={saving}
            placeholder="Shot UUID"
          />
        </label>
        <label>
          Notes
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} disabled={saving} />
        </label>
        <button type="submit" className="primary-button touch-target" disabled={saving || !label.trim()}>
          Save image plan
        </button>
        <p className="form-hint">Generate image remains disabled: planning never submits ComfyUI work.</p>
      </form>
    </div>
  )
}
