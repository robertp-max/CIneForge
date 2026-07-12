import { useEffect, useMemo, useRef, useState } from 'react'
import type { StoryboardAggregate } from '../../api/client'
import { formatDuration } from '../utils'

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value))
}

export function AnimaticModal({
  data,
  onClose,
}: {
  data: StoryboardAggregate
  onClose: () => void
}) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const lastTickRef = useRef<number | null>(null)
  const [playing, setPlaying] = useState(false)
  const [elapsedSec, setElapsedSec] = useState(0)
  const shots = useMemo(
    () => data.chapters.flatMap((chapter) => chapter.scenes.flatMap((scene) => scene.shots)),
    [data.chapters],
  )
  const timeline = useMemo(() => {
    return shots.reduce<Array<{ shot: (typeof shots)[number]; startSec: number; endSec: number }>>(
      (items, shot) => {
        const startSec = items.at(-1)?.endSec ?? 0
        return [...items, { shot, startSec, endSec: startSec + Math.max(0, shot.duration_sec) }]
      },
      [],
    )
  }, [shots])
  const totalSec = timeline.at(-1)?.endSec ?? 0
  const current =
    timeline.find((item) => elapsedSec < item.endSec) ?? timeline.at(-1) ?? null
  const currentIndex = current ? timeline.indexOf(current) : -1
  const progress = totalSec > 0 ? clamp((elapsedSec / totalSec) * 100, 0, 100) : 0

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
      if (event.key === ' ' && event.target === document.body) {
        event.preventDefault()
        setPlaying((value) => !value)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    if (!playing || totalSec <= 0) {
      lastTickRef.current = null
      return undefined
    }

    lastTickRef.current = performance.now()
    const timer = window.setInterval(() => {
      const now = performance.now()
      const previous = lastTickRef.current ?? now
      lastTickRef.current = now
      const deltaSec = (now - previous) / 1000
      setElapsedSec((value) => {
        const next = Math.min(totalSec, value + deltaSec)
        if (next >= totalSec) setPlaying(false)
        return next
      })
    }, 100)
    return () => window.clearInterval(timer)
  }, [playing, totalSec])

  function togglePlayback() {
    if (totalSec <= 0) return
    if (!playing && elapsedSec >= totalSec) setElapsedSec(0)
    setPlaying((value) => !value)
  }

  function restart() {
    setElapsedSec(0)
    setPlaying(totalSec > 0)
  }

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="animatic-title"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div className="animatic-modal">
        <button
          ref={closeRef}
          type="button"
          className="dialog-close touch-target"
          aria-label="Close animatic"
          onClick={onClose}
        >
          ×
        </button>
        <div className="animatic-frame" aria-live="polite">
          <span>NO VIDEO RENDERING</span>
          <h2 id="animatic-title">{current?.shot.title ?? 'Storyboard placeholder'}</h2>
          <p>{current?.shot.visual_description ?? 'Add a planned shot to preview timing.'}</p>
          {current ? (
            <small>
              Shot {currentIndex + 1} of {shots.length} · {current.shot.duration_sec}s
            </small>
          ) : null}
        </div>

        <div className="animatic-controls" aria-label="Animatic playback controls">
          <div className="inline-actions">
            <button
              type="button"
              className="primary-button touch-target"
              disabled={totalSec <= 0}
              aria-pressed={playing}
              onClick={togglePlayback}
            >
              {playing ? 'Pause' : elapsedSec >= totalSec && totalSec > 0 ? 'Play again' : 'Play'}
            </button>
            <button
              type="button"
              className="secondary-button touch-target"
              disabled={totalSec <= 0}
              onClick={restart}
            >
              Restart
            </button>
            <span className="mono" aria-live="off">
              {formatDuration(elapsedSec)} / {formatDuration(totalSec)}
            </span>
          </div>
          <label>
            Seek through stored shot timing
            <input
              type="range"
              min={0}
              max={Math.max(totalSec, 0.1)}
              step={0.1}
              value={Math.min(elapsedSec, Math.max(totalSec, 0.1))}
              disabled={totalSec <= 0}
              aria-valuetext={`${formatDuration(elapsedSec)} of ${formatDuration(totalSec)}`}
              onChange={(event) => {
                const next = clamp(Number(event.target.value), 0, totalSec)
                setElapsedSec(next)
                if (next >= totalSec) setPlaying(false)
              }}
            />
          </label>
          <div className="progress-bar" aria-hidden="true">
            <span style={{ width: `${progress}%` }} />
          </div>
          <div className="notice info">
            <strong>Current narration</strong>
            <p>
              {current?.shot.narration?.trim() ||
                current?.shot.narration_exception_reason?.trim() ||
                'No narration or narration exception is stored for this shot.'}
            </p>
          </div>
        </div>

        <p>
          <b>Timing prototype only — no image or video rendering.</b> This browser-only preview advances through
          persisted shot durations and narration text. It does not call ComfyUI, FFmpeg, a voice
          provider, or the job queue. {shots.length} shot{shots.length === 1 ? '' : 's'} in plan.
        </p>
      </div>
    </div>
  )
}
