import { useState } from 'react'
import { useStudio } from '../StudioContext'
import { formatDuration } from '../utils'
import { EmptyState } from '../components/StateBlocks'

export function StoryPage() {
  const { data, addHierarchy, updateStoryFields, busy } = useStudio()
  const [logline, setLogline] = useState(data?.story.logline ?? '')
  const [synopsis, setSynopsis] = useState(data?.story.synopsis ?? '')
  const [baseStory, setBaseStory] = useState(data?.story.base_story ?? '')

  if (!data) return null

  return (
    <div className="split-2">
      <div className="panel">
        <div className="panel-title">
          <div>
            <h2>Story intake</h2>
            <p>Edit planning text stored on the story record. Saving writes to the backend only.</p>
          </div>
        </div>

        <div className="stack-form" style={{ maxWidth: '100%' }}>
          <label>
            Title
            <input value={data.story.title} readOnly aria-readonly="true" />
          </label>
          <label>
            Logline
            <input
              value={logline}
              onChange={(event) => setLogline(event.target.value)}
              disabled={busy}
              placeholder="One-sentence production intent"
            />
          </label>
          <label>
            Synopsis
            <textarea
              value={synopsis}
              onChange={(event) => setSynopsis(event.target.value)}
              disabled={busy}
              placeholder="Short synopsis for review"
            />
          </label>
          <label>
            Base story
            <textarea
              value={baseStory}
              onChange={(event) => setBaseStory(event.target.value)}
              disabled={busy}
            />
          </label>
          <button
            type="button"
            className="primary-button touch-target"
            disabled={busy}
            onClick={() =>
              void updateStoryFields({
                logline: logline || null,
                synopsis: synopsis || null,
                base_story: baseStory,
              })
            }
          >
            Save story fields
          </button>
        </div>
      </div>

      <div className="panel">
        <div className="panel-title">
          <div>
            <h2>Ordered structure</h2>
            <p>Chapter → scene → shot hierarchy as stored on the server.</p>
          </div>
        </div>

        <div className="story-actions" style={{ marginBottom: 14 }}>
          <button type="button" disabled={busy} onClick={() => void addHierarchy('chapter')}>
            Add chapter
          </button>
          <button type="button" disabled={busy} onClick={() => void addHierarchy('scene')}>
            Add scene
          </button>
          <button type="button" disabled={busy} onClick={() => void addHierarchy('shot')}>
            Add shot
          </button>
        </div>

        {!data.chapters.length ? (
          <EmptyState title="No chapters" detail="Create the first chapter to structure the story." />
        ) : (
          <ol className="story-tree">
            {data.chapters.map((chapter, chapterIndex) => (
              <li key={chapter.id}>
                <b>
                  CH{String(chapterIndex + 1).padStart(2, '0')} · {chapter.title}
                </b>
                <span>
                  {' '}
                  {chapter.summary ?? 'No chapter summary yet.'} · {formatDuration(chapter.duration_sec)}
                </span>
                <ol className="story-tree">
                  {chapter.scenes.map((scene, sceneIndex) => (
                    <li key={scene.id}>
                      <b>
                        SC{String(sceneIndex + 1).padStart(2, '0')} · {scene.title}
                      </b>
                      <span>
                        {' '}
                        {scene.shots.length} shot{scene.shots.length === 1 ? '' : 's'} ·{' '}
                        {formatDuration(scene.duration_sec)}
                      </span>
                      <ol className="story-tree">
                        {scene.shots.map((shot) => (
                          <li key={shot.id}>
                            {shot.display_label} · {shot.title} ({shot.duration_sec}s) ·{' '}
                            {shot.approval_state}
                          </li>
                        ))}
                      </ol>
                    </li>
                  ))}
                </ol>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  )
}
