import { useEffect, useRef } from 'react'
import type { StoryboardAggregate } from '../../api/client'

export function AnimaticModal({
  data,
  onClose,
}: {
  data: StoryboardAggregate
  onClose: () => void
}) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const shots = data.chapters.flatMap((chapter) =>
    chapter.scenes.flatMap((scene) => scene.shots),
  )
  const first = shots[0]

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Preview animatic"
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
        <div className="animatic-frame">
          <span>NO VIDEO RENDERING</span>
          <h2>{first?.title ?? 'Storyboard placeholder'}</h2>
          <p>{first?.visual_description ?? 'Add a planned shot to preview timing.'}</p>
        </div>
        <p>
          <b>Timing prototype only — no video rendering.</b> This browser preview uses shot timing and
          placeholders only. It does not call ComfyUI, FFmpeg, or the job queue. {shots.length} shot
          {shots.length === 1 ? '' : 's'} in plan.
        </p>
      </div>
    </div>
  )
}
