import { useEffect, useState } from 'react'
import type { Shot } from '../../api/client'
import { useStudio } from '../StudioContext'
import { formatDuration } from '../utils'
import { EmptyState } from '../components/StateBlocks'

type InspectorTab = 'details' | 'prompts' | 'technical'

export function StoryboardPage() {
  const { data, selectedShot, setSelectedShot, addHierarchy, saveShot, busy } = useStudio()
  const [tab, setTab] = useState<InspectorTab>('details')
  const [draft, setDraft] = useState<Shot | null>(null)

  useEffect(() => {
    setDraft(selectedShot)
    setTab('details')
  }, [selectedShot])

  if (!data) return null

  const onSave = () => {
    if (!draft) return
    void saveShot(draft.id, {
      title: draft.title,
      duration_sec: draft.duration_sec,
      duration_override_reason: draft.duration_override_reason,
      visual_description: draft.visual_description,
      narration: draft.narration,
      prompt_positive: draft.prompt_positive,
      prompt_negative: draft.prompt_negative,
      camera_notes: draft.camera_notes,
      lighting_notes: draft.lighting_notes,
      technical_notes: draft.technical_notes,
      continuity_source_shot_id: draft.continuity_source_shot_id,
    })
  }

  return (
    <div className="storyboard-layout">
      <div>
        <div className="toolbar">
          <span>Ordered hierarchy · display labels are cosmetic; UUIDs remain identity.</span>
          <div>
            <button type="button" className="touch-target" disabled={busy} onClick={() => void addHierarchy('chapter')}>
              + Chapter
            </button>
            <button type="button" className="touch-target" disabled={busy} onClick={() => void addHierarchy('scene')}>
              + Scene
            </button>
            <button type="button" className="touch-target" disabled={busy} onClick={() => void addHierarchy('shot')}>
              + Shot
            </button>
          </div>
        </div>

        {!data.chapters.length ? (
          <EmptyState
            title="No chapters yet"
            detail="Add a chapter to begin the ordered production hierarchy."
            action={
              <button type="button" className="primary-button" disabled={busy} onClick={() => void addHierarchy('chapter')}>
                Add chapter
              </button>
            }
          />
        ) : (
          data.chapters.map((chapter, index) => (
            <article className="chapter-group" key={chapter.id}>
              <header>
                <span>CH{String(index + 1).padStart(2, '0')}</span>
                <b>{chapter.title}</b>
                <small>{formatDuration(chapter.duration_sec)}</small>
              </header>
              {chapter.scenes.map((scene, sceneIndex) => (
                <section key={scene.id} aria-label={`Scene ${scene.title}`}>
                  <div className="scene-name">
                    <span>
                      SC{String(sceneIndex + 1).padStart(2, '0')} · {scene.title}
                    </span>
                    <small>{formatDuration(scene.duration_sec)}</small>
                  </div>
                  <div className="shot-row" role="list">
                    {scene.shots.map((shot) => (
                      <button
                        key={shot.id}
                        type="button"
                        role="listitem"
                        className={`shot-card ${selectedShot?.id === shot.id ? 'selected' : ''}`}
                        aria-pressed={selectedShot?.id === shot.id}
                        onClick={() => setSelectedShot(shot)}
                      >
                        <span>
                          SH{String(shot.order_index + 1).padStart(2, '0')} · {shot.display_label}
                        </span>
                        <b>{shot.title}</b>
                        <small>
                          {shot.duration_sec}s · {shot.approval_state}
                          {shot.blocked_reason ? ` · ${shot.blocked_reason}` : ''}
                        </small>
                      </button>
                    ))}
                    {!scene.shots.length ? (
                      <p className="form-hint" style={{ margin: 0 }}>
                        No shots in this scene.
                      </p>
                    ) : null}
                  </div>
                </section>
              ))}
              {!chapter.scenes.length ? (
                <section>
                  <p className="form-hint">No scenes in this chapter yet.</p>
                </section>
              ) : null}
            </article>
          ))
        )}
      </div>

      <aside className="inspector" aria-label="Shot inspector">
        <h2>Shot inspector</h2>
        {draft ? (
          <>
            <p className="eyebrow mono">{draft.id}</p>

            <div className="inspector-tabs" role="tablist" aria-label="Inspector sections">
              {(
                [
                  ['details', 'Details'],
                  ['prompts', 'Prompts'],
                  ['technical', 'Technical'],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={tab === id}
                  onClick={() => setTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>

            {tab === 'details' ? (
              <div role="tabpanel">
                <label>
                  Title
                  <input
                    value={draft.title}
                    onChange={(event) => setDraft({ ...draft, title: event.target.value })}
                    disabled={busy}
                  />
                </label>
                <label>
                  Duration (sec)
                  <input
                    type="number"
                    min={0.1}
                    step={0.1}
                    value={draft.duration_sec}
                    onChange={(event) =>
                      setDraft({ ...draft, duration_sec: Number(event.target.value) })
                    }
                    disabled={busy}
                  />
                </label>
                <label>
                  Override reason
                  <input
                    value={draft.duration_override_reason ?? ''}
                    onChange={(event) =>
                      setDraft({ ...draft, duration_override_reason: event.target.value || null })
                    }
                    disabled={busy}
                  />
                </label>
                <label>
                  Visual description
                  <textarea
                    value={draft.visual_description ?? ''}
                    onChange={(event) =>
                      setDraft({ ...draft, visual_description: event.target.value || null })
                    }
                    disabled={busy}
                  />
                </label>
                <label>
                  Narration
                  <textarea
                    value={draft.narration ?? ''}
                    onChange={(event) => setDraft({ ...draft, narration: event.target.value || null })}
                    disabled={busy}
                  />
                </label>
              </div>
            ) : null}

            {tab === 'prompts' ? (
              <div role="tabpanel">
                <p className="form-hint">
                  Prompts are planning text only. Generation-model selection is separate and remains
                  unverified until runtime registry data exists.
                </p>
                <label>
                  Positive prompt
                  <textarea
                    value={draft.prompt_positive ?? ''}
                    onChange={(event) =>
                      setDraft({ ...draft, prompt_positive: event.target.value || null })
                    }
                    disabled={busy}
                  />
                </label>
                <label>
                  Negative prompt
                  <textarea
                    value={draft.prompt_negative ?? ''}
                    onChange={(event) =>
                      setDraft({ ...draft, prompt_negative: event.target.value || null })
                    }
                    disabled={busy}
                  />
                </label>
              </div>
            ) : null}

            {tab === 'technical' ? (
              <div role="tabpanel">
                <label>
                  Camera notes
                  <textarea
                    value={draft.camera_notes ?? ''}
                    onChange={(event) =>
                      setDraft({ ...draft, camera_notes: event.target.value || null })
                    }
                    disabled={busy}
                  />
                </label>
                <label>
                  Lighting notes
                  <textarea
                    value={draft.lighting_notes ?? ''}
                    onChange={(event) =>
                      setDraft({ ...draft, lighting_notes: event.target.value || null })
                    }
                    disabled={busy}
                  />
                </label>
                <label>
                  Technical notes
                  <textarea
                    value={draft.technical_notes ?? ''}
                    onChange={(event) =>
                      setDraft({ ...draft, technical_notes: event.target.value || null })
                    }
                    disabled={busy}
                  />
                </label>
                <label>
                  Continuity source shot ID
                  <input
                    value={draft.continuity_source_shot_id ?? ''}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        continuity_source_shot_id: event.target.value || null,
                      })
                    }
                    disabled={busy}
                    className="mono"
                  />
                </label>
                <ul className="kv-list">
                  <li>
                    <span>Approval</span>
                    <strong>{draft.approval_state}</strong>
                  </li>
                  <li>
                    <span>Production</span>
                    <strong>{draft.production_status}</strong>
                  </li>
                </ul>
              </div>
            ) : null}

            <div className="inline-actions" style={{ marginTop: 14 }}>
              <button type="button" className="primary-button touch-target" disabled={busy} onClick={onSave}>
                Save shot
              </button>
            </div>
          </>
        ) : (
          <p>Select a shot to inspect persisted details, prompts, and technical planning information.</p>
        )}
      </aside>
    </div>
  )
}
