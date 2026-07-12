import { useState, type FormEvent } from 'react'
import { useStudio } from '../StudioContext'

export function StoryBootstrap() {
  const {
    projectId,
    setProjectId,
    storyId,
    setStoryId,
    message,
    createStory,
    loadExistingStory,
    busy,
    error,
    backendStatus,
  } = useStudio()
  const [loadError, setLoadError] = useState<string | null>(null)

  const onLoad = async (event: FormEvent) => {
    event.preventDefault()
    setLoadError(null)
    try {
      await loadExistingStory(storyId)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Could not load story.')
    }
  }

  return (
    <section className="studio page">
      <header className="page-header studio-header">
        <div>
          <span className="eyebrow">PRODUCTION PLAN · PHASE 1</span>
          <h1>Storyboard Phase 1</h1>
          <p>
            Create the planning record that connects an existing CineForge project to its story, chapters,
            scenes, and shots. Server state is canonical — nothing is stored as source of truth in the
            browser.
          </p>
        </div>
      </header>

      <div className="notice warning" role="status">
        Backend status: <strong>{backendStatus}</strong>. Planning never queues renders, installs
        workflows, clones voices, or generates audio automatically.
      </div>

      <div className="split-2">
        <form className="panel studio-form" onSubmit={(event) => void createStory(event)}>
          <div className="panel-title full-span" style={{ gridColumn: '1 / -1' }}>
            <div>
              <h2>Create planning story</h2>
              <p>Requires an existing project UUID from the Projects API.</p>
            </div>
          </div>

          <label>
            Existing project ID
            <input
              required
              name="project_id"
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              placeholder="Paste a Project UUID"
              autoComplete="off"
              disabled={busy}
            />
          </label>

          <label>
            Story title
            <input required name="title" placeholder="A New Journey" disabled={busy} />
          </label>

          <label>
            Target runtime (seconds)
            <input
              required
              name="target_duration_sec"
              type="number"
              min={1}
              defaultValue={225}
              disabled={busy}
            />
          </label>

          <label className="full-span">
            Source story
            <textarea
              required
              name="base_story"
              placeholder="The narrative and production intent supplied by the user."
              disabled={busy}
            />
          </label>

          <button className="primary-button touch-target" disabled={busy}>
            {busy ? 'Working…' : 'Create planning story'}
          </button>
        </form>

        <form className="panel stack-form" onSubmit={(event) => void onLoad(event)}>
          <div className="panel-title">
            <div>
              <h2>Load existing story</h2>
              <p>Paste a story UUID already stored on the backend.</p>
            </div>
          </div>
          <label>
            Story ID
            <input
              required
              value={storyId}
              onChange={(event) => setStoryId(event.target.value)}
              placeholder="Story UUID"
              autoComplete="off"
              disabled={busy}
            />
          </label>
          <button type="submit" className="secondary-button touch-target" disabled={busy}>
            Load story
          </button>
          {loadError ? (
            <p className="notice error" role="alert">
              {loadError}
            </p>
          ) : null}
        </form>
      </div>

      <p className="notice info" role="status">
        {message}
      </p>
      {error ? (
        <p className="notice error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  )
}
