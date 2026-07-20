import { useState, type FormEvent, type KeyboardEvent } from 'react'
import type { PageId } from './AppShell'

type StudioHomeHeroProps = {
  onNavigateStudio: (page: PageId) => void
  onNotify?: (message: string) => void
}

const destinations: { page: PageId; label: string; pattern: RegExp }[] = [
  { page: 'story', label: 'Story & chapters', pattern: /story|script|chapter|narration|treatment/ },
  { page: 'storyboard', label: 'Storyboard', pattern: /storyboard|shot|scene|frame|timing|camera/ },
  { page: 'characters', label: 'Characters', pattern: /character|cast|identity/ },
  { page: 'voices', label: 'Voices', pattern: /voice|audio|speech|dialogue|speaker/ },
  { page: 'images', label: 'Starting images', pattern: /image|reference|visual|picture|continuity/ },
  { page: 'routing', label: 'Model routing', pattern: /model|route|routing|gpu|checkpoint/ },
  { page: 'workflows', label: 'Workflows', pattern: /workflow|comfy|pipeline|node/ },
  { page: 'exports', label: 'Exports', pattern: /export|render|deliver|output|final/ },
  { page: 'settings', label: 'Project settings', pattern: /setting|runtime|preference|configuration/ },
]

const quickLinks: { page: PageId; label: string; icon: string }[] = [
  { page: 'storyboard', label: 'Storyboard', icon: '▤' },
  { page: 'characters', label: 'Characters', icon: '♙' },
  { page: 'images', label: 'Starting images', icon: '▧' },
  { page: 'workflows', label: 'Workflows', icon: '◇' },
  { page: 'overview', label: 'All seven phases', icon: '✦' },
]

export function StudioHomeHero({ onNavigateStudio, onNotify }: StudioHomeHeroProps) {
  const [prompt, setPrompt] = useState('')

  const openDestination = (value = prompt) => {
    const normalized = value.trim().toLowerCase()
    const destination = destinations.find((item) => item.pattern.test(normalized)) ?? {
      page: 'overview' as PageId,
      label: 'Seven-phase overview',
    }
    onNavigateStudio(destination.page)
    onNotify?.(normalized ? `Opening ${destination.label}` : 'Opening the seven-phase production workspace')
  }

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    openDestination()
  }

  const submitShortcut = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  return (
    <section className="studio-home-hero" aria-labelledby="studio-home-title">
      <div className="studio-home-heading">
        <h1 id="studio-home-title">Shape every frame with CineForge</h1>
        <span className="studio-hero-spark" aria-hidden="true">✦</span>
      </div>
      <p>Move from story planning to final assembly in one controlled production workspace.</p>
      <form className="studio-composer" onSubmit={submit}>
        <textarea
          rows={2}
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          onKeyDown={submitShortcut}
          aria-label="Describe the CineForge workspace you want to open"
          placeholder="Describe what you want to work on, or name a production workspace…"
        />
        <footer>
          <div className="studio-composer-tools">
            <button type="button" onClick={() => onNavigateStudio('voices')} aria-label="Open voice workspace" title="Open voice workspace">
              ♬
            </button>
            <button type="button" onClick={() => onNavigateStudio('images')} aria-label="Open starting images" title="Open starting images">
              ＋
            </button>
          </div>
          <span className="studio-local-note">
            <i />
            Local navigator · no model call
          </span>
          <button className="studio-build-button" type="submit">
            <span>✦</span>
            <span>{prompt.trim() ? 'Open workspace' : "I'm feeling cinematic"}</span>
            <kbd>Ctrl</kbd>
            <kbd>↵</kbd>
          </button>
        </footer>
      </form>
      <nav className="studio-suggestion-row" aria-label="Production workspace shortcuts">
        {quickLinks.map((item) => (
          <button
            key={item.page}
            type="button"
            onClick={() => {
              onNavigateStudio(item.page)
              onNotify?.(`Opening ${item.label}`)
            }}
          >
            <span aria-hidden="true">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </section>
  )
}
