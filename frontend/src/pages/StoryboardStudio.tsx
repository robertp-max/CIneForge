import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, api, type Readiness, type StoryboardAggregate } from '../api/client'

export type StudioPage = 'overview' | 'storyboard' | 'story' | 'characters' | 'voices' | 'images' | 'routing' | 'workflows' | 'exports' | 'settings'

const formatDuration = (value: number) => `${Math.floor(value / 60)}:${String(Math.round(value % 60)).padStart(2, '0')}`

export function StoryboardStudio({ page }: { page: StudioPage }) {
  const [projectId, setProjectId] = useState('')
  const [storyId, setStoryId] = useState('')
  const [data, setData] = useState<StoryboardAggregate | null>(null)
  const [readiness, setReadiness] = useState<Readiness | null>(null)
  const [message, setMessage] = useState('Choose a project and create or select a Storyboard Phase A story.')
  const [selectedShot, setSelectedShot] = useState<StoryboardAggregate['chapters'][number]['scenes'][number]['shots'][number] | null>(null)
  const [animatic, setAnimatic] = useState(false)

  const reload = useCallback(async (id = storyId) => {
    if (!id) return
    try {
      const [aggregate, nextReadiness] = await Promise.all([api.aggregate(id), api.readiness(id)])
      setData(aggregate)
      setReadiness(nextReadiness)
      setMessage('Live planning data loaded from the CineForge backend.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to load storyboard data.')
    }
  }, [storyId])

  const createStory = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    try {
      const story = await api.createStory({ project_id: String(form.get('project_id')), title: String(form.get('title')), base_story: String(form.get('base_story')), target_duration_sec: Number(form.get('target_duration_sec')) })
      setProjectId(story.project_id); setStoryId(story.id); await reload(story.id)
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not create Story.') }
  }

  const addHierarchy = async (kind: 'chapter' | 'scene' | 'shot') => {
    if (!data) return
    const title = window.prompt(`New ${kind} title`)
    if (!title?.trim()) return
    try {
      if (kind === 'chapter') await api.createChapter(data.story.id, { title, order_index: data.chapters.length })
      if (kind === 'scene') {
        const chapter = data.chapters[0]; if (!chapter) throw new Error('Create a Chapter before adding a Scene.')
        await api.createScene(chapter.id, { title, order_index: chapter.scenes.length })
      }
      if (kind === 'shot') {
        const scene = data.chapters[0]?.scenes[0]; if (!scene) throw new Error('Create a Scene before adding a Shot.')
        const duration = Number(window.prompt('Shot duration in seconds (normal range 6–12)', '8'))
        const reason = duration < 6 || duration > 12 ? window.prompt('Override reason is required') ?? '' : undefined
        await api.createShot(scene.id, { title, duration_sec: duration, duration_override_reason: reason, order_index: scene.shots.length })
      }
      await reload()
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not add planning item.') }
  }

  const addCharacter = async () => {
    if (!data) return
    const name = window.prompt('Character name'); if (!name?.trim()) return
    try { await api.createCharacter(data.story.id, { name }); await reload() } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not add character.') }
  }
  const addVoice = async () => {
    if (!data) return
    const name = window.prompt('Voice profile name'); if (!name?.trim()) return
    try { await api.createVoice(data.story.id, { name, source_type: 'placeholder', consent_required: false, consent_confirmed: false }); await reload() } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not add voice profile.') }
  }

  const planned = readiness?.planned_duration_sec ?? 0
  if (!data) return <section className="studio page"><StudioHeader title="Storyboard Phase A" description="Create the planning record that connects an existing CineForge Project to its Story, Chapters, Scenes, and Shots." /><form className="panel studio-form" onSubmit={createStory}><label>Existing project ID<input required name="project_id" value={projectId} onChange={(event) => setProjectId(event.target.value)} placeholder="Paste a Project UUID from Projects" /></label><label>Story title<input required name="title" placeholder="A New Journey" /></label><label>Target runtime (seconds)<input required name="target_duration_sec" type="number" min="1" defaultValue="225" /></label><label>Source story<textarea required name="base_story" placeholder="The narrative and production intent supplied by the user." /></label><button className="primary-button">Create planning story</button></form><p className="notice info">{message}</p></section>

  const content = {
    overview: <Overview data={data} readiness={readiness} onApprove={async () => { try { await api.approveStoryboard(data.story.id, 'Producer'); await reload(); setMessage('Production plan approved. No rendering was enqueued.') } catch (error) { if (error instanceof ApiError && Array.isArray((error.detail as { detail?: unknown }).detail)) setMessage('Approval blocked by backend readiness gates.'); else setMessage(error instanceof Error ? error.message : 'Approval failed.') } }} />,
    storyboard: <Storyboard data={data} selected={selectedShot} onSelect={setSelectedShot} onAdd={addHierarchy} onSave={async () => { if (!selectedShot) return; try { await api.updateShot(selectedShot.id, { ...selectedShot }); await reload(); setMessage('Shot details saved to the backend.') } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not save shot.') } }} />,
    story: <StoryPage data={data} onAdd={addHierarchy} />, characters: <PeoplePage title="Characters" description="Identity references and character bibles are planning records; image generation is unavailable in Phase A." items={data.characters} onAdd={addCharacter} />, voices: <VoicesPage data={data} onAdd={addVoice} />,
    images: <FuturePage title="Starting Images" description="Plan approved reference assets and starting-image requirements here. Generate image remains disabled: storyboard planning never submits ComfyUI work." />, routing: <FuturePage title="Model Routing" description="Provider models are proposal-only. Generation model and workflow recommendations are shown as Unknown until real registry and benchmark data exist." />, workflows: <FuturePage title="Workflows" description="Workflow readiness comes from the backend runtime registry. This screen never claims a workflow is installed, validated, or benchmarked without evidence." />,
    exports: <ExportsPage storyId={data.story.id} />, settings: <FuturePage title="Project Settings" description="Phase A policy settings—duration range, approval policy, continuity, consent, aspect ratio, and render approval—are planned for persisted configuration. Runtime configuration remains read-only." />,
  }[page]

  return <section className="studio page"><StudioHeader title={page === 'story' ? 'Story & Chapters' : page[0].toUpperCase() + page.slice(1)} description={`${data.story.title} · Storyboard Phase A · ${formatDuration(planned)} planned / ${formatDuration(data.story.target_duration_sec)} target`} actions={<><button className="secondary-button" onClick={() => void reload()}>Refresh</button><button className="primary-button" onClick={() => setAnimatic(true)}>Preview animatic</button></>} /><p className="studio-message" role="status">{message}</p>{content}{animatic ? <Animatic data={data} onClose={() => setAnimatic(false)} /> : null}</section>
}

function StudioHeader({ title, description, actions }: { title: string; description: string; actions?: React.ReactNode }) { return <header className="page-header studio-header"><div><span className="eyebrow">PRODUCTION PLAN · PHASE A</span><h1>{title}</h1><p>{description}</p></div><div className="page-actions">{actions}</div></header> }
function Overview({ data, readiness, onApprove }: { data: StoryboardAggregate; readiness: Readiness | null; onApprove: () => void }) { const metrics = [['Chapters', data.chapters.length], ['Scenes', data.chapters.reduce((n, c) => n + c.scenes.length, 0)], ['Shots', data.chapters.reduce((n, c) => n + c.scenes.reduce((s, scene) => s + scene.shots.length, 0), 0)], ['Characters', data.characters.length], ['Voice profiles', data.voices.length]]; return <><div className="studio-metrics">{metrics.map(([label, value]) => <article key={String(label)}><span>{label}</span><strong>{value}</strong></article>)}<article><span>Readiness</span><strong>{readiness?.ready ? 'Ready' : 'Review'}</strong></article></div><div className="panel"><h2>Backend readiness gates</h2><p>Approval creates an immutable storyboard version only. It never creates a Timeline Slot, Clip Iteration, queue job, ComfyUI submission, or FFmpeg job.</p><ul className="gate-list">{readiness?.reasons.length ? readiness.reasons.map((reason) => <li key={reason.code + reason.entity_id}><b>{reason.code}</b><span>{reason.message}</span></li>) : <li><b>ready</b><span>All current backend readiness checks pass.</span></li>}</ul><button className="primary-button" onClick={onApprove}>Approve production plan</button></div></> }
function Storyboard({ data, selected, onSelect, onAdd, onSave }: { data: StoryboardAggregate; selected: StoryboardAggregate['chapters'][number]['scenes'][number]['shots'][number] | null; onSelect: (shot: StoryboardAggregate['chapters'][number]['scenes'][number]['shots'][number]) => void; onAdd: (kind: 'chapter' | 'scene' | 'shot') => void; onSave: () => void }) { return <div className="storyboard-layout"><div><div className="toolbar"><span>Ordered hierarchy · A/B/C are display labels; UUIDs remain the identity.</span><div><button onClick={() => void onAdd('chapter')}>+ Chapter</button><button onClick={() => void onAdd('scene')}>+ Scene</button><button onClick={() => void onAdd('shot')}>+ Shot</button></div></div>{data.chapters.map((chapter, index) => <article className="chapter-group" key={chapter.id}><header><span>CH{String(index + 1).padStart(2, '0')}</span><b>{chapter.title}</b><small>{formatDuration(chapter.duration_sec)}</small></header>{chapter.scenes.map((scene, sceneIndex) => <section key={scene.id}><div className="scene-name">SC{String(sceneIndex + 1).padStart(2, '0')} · {scene.title} <small>{formatDuration(scene.duration_sec)}</small></div><div className="shot-row">{scene.shots.map((shot) => <button key={shot.id} className={`shot-card ${selected?.id === shot.id ? 'selected' : ''}`} onClick={() => onSelect(shot)}><span>SH{String(shot.order_index + 1).padStart(2, '0')} · {shot.display_label}</span><b>{shot.title}</b><small>{shot.duration_sec}s · {shot.approval_state}</small></button>)}</div></section>)}</article>)}</div><aside className="inspector"><h2>Shot inspector</h2>{selected ? <><p className="eyebrow">{selected.id}</p><label>Title<input value={selected.title} readOnly /></label><label>Duration<input value={selected.duration_sec} readOnly /></label><label>Details<textarea value={selected.visual_description ?? ''} readOnly /></label><div className="inspector-tabs"><b>Details</b><span>Prompts</span><span>Technical</span></div><p>Prompts are planning text only. Generation-model selection is separate and remains unverified until runtime data exists.</p><button className="primary-button" onClick={onSave}>Save shot</button></> : <p>Select a Shot to inspect persisted Details, Prompts, and Technical planning information.</p>}</aside></div> }
function StoryPage({ data, onAdd }: { data: StoryboardAggregate; onAdd: (kind: 'chapter' | 'scene' | 'shot') => void }) { return <div className="panel"><h2>Story intake and ordered structure</h2><p>{data.story.base_story}</p><div className="story-actions"><button onClick={() => void onAdd('chapter')}>Add chapter</button><button onClick={() => void onAdd('scene')}>Add scene</button><button onClick={() => void onAdd('shot')}>Add shot</button></div><ol>{data.chapters.map((chapter) => <li key={chapter.id}><b>{chapter.title}</b><span>{chapter.summary ?? 'No chapter summary yet.'}</span></li>)}</ol></div> }
function PeoplePage({ title, description, items, onAdd }: { title: string; description: string; items: StoryboardAggregate['characters']; onAdd: () => void }) { return <div className="panel"><div className="panel-title"><div><h2>{title}</h2><p>{description}</p></div><button className="primary-button" onClick={onAdd}>Add character</button></div><div className="people-grid">{items.map((item) => <article key={item.id}><span className="avatar">{item.name.slice(0, 2).toUpperCase()}</span><b>{item.name}</b><small>{item.role ?? 'Role not specified'} · {item.approval_state}</small><p>Reference assets are planned and reviewed here; no asset is generated automatically.</p></article>)}{!items.length ? <p>No characters yet.</p> : null}</div></div> }
function VoicesPage({ data, onAdd }: { data: StoryboardAggregate; onAdd: () => void }) { return <div className="panel"><div className="panel-title"><div><h2>Voice profiles</h2><p>User-provided voice sources require confirmed consent. Voice cloning is not available.</p></div><button className="primary-button" onClick={onAdd}>Add placeholder voice</button></div><div className="people-grid">{data.voices.map((voice) => <article key={voice.id}><b>{voice.name}</b><small>{voice.source_type}</small><p>{voice.consent_confirmed ? 'Consent confirmed' : 'No consent required or not confirmed'}</p></article>)}</div></div> }
function FuturePage({ title, description }: { title: string; description: string }) { return <div className="panel disabled-future"><h2>{title}</h2><p>{description}</p><button disabled aria-describedby="future-explanation">Unavailable in Storyboard Phase A</button><small id="future-explanation">This control is intentionally unavailable and does not perform any background action.</small></div> }
function ExportsPage({ storyId }: { storyId: string }) { const jsonUrl = `${apiBase()}/storyboard/stories/${storyId}/export.json`; const csvUrl = `${apiBase()}/storyboard/stories/${storyId}/shot-list.csv`; return <div className="panel"><h2>Planning exports</h2><p>These exports contain the stored planning hierarchy. PDF, EDL, render package, and media outputs remain unavailable because Phase A does not render.</p><div className="story-actions"><a className="primary-button" href={jsonUrl}>Storyboard JSON</a><a className="secondary-button" href={csvUrl}>Shot List CSV</a><button disabled>PDF export — future phase</button></div></div> }
function Animatic({ data, onClose }: { data: StoryboardAggregate; onClose: () => void }) { const first = data.chapters.flatMap((chapter) => chapter.scenes.flatMap((scene) => scene.shots))[0]; return <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Preview animatic"><div className="animatic-modal"><button aria-label="Close animatic" onClick={onClose}>×</button><div className="animatic-frame"><span>NO VIDEO RENDERING</span><h2>{first?.title ?? 'Storyboard placeholder'}</h2><p>{first?.visual_description ?? 'Add a planned Shot to preview timing.'}</p></div><p><b>Timing prototype only — no video rendering.</b> This browser preview uses shot timing and placeholders; it does not call ComfyUI or FFmpeg.</p></div></div> }
function apiBase() { return import.meta.env.VITE_CINEFORGE_API_BASE_URL?.replace(/\/$/, '') ?? 'http://127.0.0.1:8000' }
