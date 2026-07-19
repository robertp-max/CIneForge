import { useMemo, useState } from 'react'

import type { PageId } from '../../components/AppShell'
import type {
  Character,
  ProductionPhase,
  Scene,
  Shot,
  StoryboardAggregate,
} from '../../api/client'
import { formatDuration, initials } from '../utils'
import { ManagedAssetImage } from './ManagedAssetImage'

type PreviewProps = {
  phase: ProductionPhase
  data: StoryboardAggregate | null
  onNavigate?: (page: PageId) => void
}

type SceneRow = {
  chapterTitle: string
  scene: Scene
  sceneNumber: number
}

type ShotRow = {
  chapterTitle: string
  sceneId: string
  sceneTitle: string
  sceneNumber: number
  shotNumber: number
  code: string
  shot: Shot
}

const NINE_PANEL_LABELS = [
  'Full body',
  'Front portrait',
  'Three-quarter',
  'Side profile',
  'Neutral',
  'Concerned',
  'Overwhelmed',
  'Focused',
  'Reflective',
] as const

const WORKFLOW_STATES = [
  ['Available', 'Registered and visible in the runtime catalog.'],
  ['Admitted', 'Validated for this production profile.'],
  ['Benchmark required', 'Evidence must be recorded before execution.'],
  ['Blocked', 'A policy or validation condition prevents execution.'],
  ['Unavailable', 'Not present in the current runtime.'],
] as const

function flattenScenes(data: StoryboardAggregate | null): SceneRow[] {
  let sceneNumber = 0
  return (data?.chapters ?? []).flatMap((chapter) =>
    chapter.scenes.map((scene) => ({
      chapterTitle: chapter.title,
      scene,
      sceneNumber: ++sceneNumber,
    })),
  )
}

function shotLetter(index: number): string {
  if (index < 26) return String.fromCharCode(65 + index)
  return String(index + 1)
}

function flattenShots(scenes: SceneRow[]): ShotRow[] {
  return scenes.flatMap((row) =>
    row.scene.shots.map((shot, index) => ({
      chapterTitle: row.chapterTitle,
      sceneId: row.scene.id,
      sceneTitle: row.scene.title,
      sceneNumber: row.sceneNumber,
      shotNumber: index + 1,
      code: `S${String(row.sceneNumber).padStart(2, '0')}${shotLetter(index)}`,
      shot,
    })),
  )
}

function lifecycleLabel(value: string): string {
  return value.replaceAll('_', ' ')
}

function PhasePreviewHeader({
  phase,
  description,
  source,
  actions,
  onNavigate,
}: {
  phase: ProductionPhase
  description: string
  source: 'Live records' | 'Derived preview' | 'Design template'
  actions?: Array<{ label: string; page: PageId }>
  onNavigate?: (page: PageId) => void
}) {
  return (
    <div className="phase-preview-header">
      <div>
        <span className="eyebrow">PHASE {phase.phase_number} · {source.toUpperCase()}</span>
        <h2>{phase.name}</h2>
        <p>{description}</p>
      </div>
      <div className="phase-preview-header-meta">
        <span className="design-available-pill">Design available</span>
        <small>Backend state · {lifecycleLabel(phase.lifecycle_state)}</small>
        {actions?.length && onNavigate ? (
          <div className="phase-preview-actions" aria-label="Related workspaces">
            {actions.map((action) => (
              <button key={action.page} type="button" onClick={() => onNavigate(action.page)}>
                {action.label} <span aria-hidden="true">↗</span>
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function WorkspaceMetric({ label, value, detail }: { label: string; value: string | number; detail?: string }) {
  return (
    <article className="phase-workspace-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </article>
  )
}

function PreviewDisclosure() {
  return (
    <div className="phase-design-disclosure" role="note">
      <span aria-hidden="true">◇</span>
      <div>
        <b>Interactive UI/UX preview</b>
        <p>This workspace reads current planning records for display. It does not start generation, submit jobs, call ComfyUI, synthesize voices, or run FFmpeg.</p>
      </div>
    </div>
  )
}

function EmptyDesignState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="phase-design-empty">
      <span aria-hidden="true">＋</span>
      <div><b>{title}</b><p>{detail}</p></div>
    </div>
  )
}

function PhaseTwoPreview({ phase, data, onNavigate }: PreviewProps) {
  const scenes = useMemo(() => flattenScenes(data), [data])
  const shots = useMemo(() => flattenShots(scenes), [scenes])
  const [selectedSceneId, setSelectedSceneId] = useState(scenes[0]?.scene.id ?? '')
  const selectedScene = scenes.find((item) => item.scene.id === selectedSceneId) ?? scenes[0] ?? null
  const selectedShots = selectedScene
    ? shots.filter((item) => item.sceneId === selectedScene.scene.id)
    : []
  const target = data?.story.target_duration_sec ?? 0
  const planned = shots.reduce((total, row) => total + Number(row.shot.duration_sec), 0)
  const average = shots.length ? planned / shots.length : 0
  const continuityCount = shots.filter((row) => row.shot.continuity_source_shot_id).length
  const startFrameCount = shots.filter((row) => row.shot.starting_image_required).length

  return (
    <div className="phase-preview-workspace">
      <PhasePreviewHeader
        phase={phase}
        source="Live records"
        description="Shape the approved narrative into a timed Chapter → Scene → Shot structure, then inspect duration, continuity, cast, and starting-frame intent in one place."
        actions={[{ label: 'Open full Storyboard', page: 'storyboard' }]}
        onNavigate={onNavigate}
      />
      <PreviewDisclosure />
      <div className="phase-workspace-metrics five">
        <WorkspaceMetric label="Chapters / acts" value={data?.chapters.length ?? '—'} />
        <WorkspaceMetric label="Scenes" value={scenes.length || '—'} />
        <WorkspaceMetric label="Shots" value={shots.length || '—'} detail={shots.length ? `${average.toFixed(1)}s average` : undefined} />
        <WorkspaceMetric label="Planned runtime" value={planned ? formatDuration(planned) : '—'} detail={target ? `${formatDuration(target)} target` : undefined} />
        <WorkspaceMetric label="Continuity links" value={shots.length ? continuityCount : '—'} detail={shots.length ? `${startFrameCount} start-frame requirements` : undefined} />
      </div>

      {scenes.length ? (
        <div className="phase-segmentation-layout">
          <aside className="phase-scene-browser" aria-label="Scene browser">
            <div className="phase-subheading"><span>STRUCTURE</span><b>{scenes.length} scenes</b></div>
            <div className="phase-scene-list">
              {scenes.map((row) => (
                <button
                  key={row.scene.id}
                  type="button"
                  className={row.scene.id === selectedScene?.scene.id ? 'active' : ''}
                  onClick={() => setSelectedSceneId(row.scene.id)}
                >
                  <span>{String(row.sceneNumber).padStart(2, '0')}</span>
                  <div><b>{row.scene.title}</b><small>{row.scene.shots.length} shots · {formatDuration(row.scene.duration_sec)}</small></div>
                </button>
              ))}
            </div>
          </aside>

          <section className="phase-shot-planner">
            <div className="phase-subheading">
              <div><span>SCENE {String(selectedScene?.sceneNumber ?? 0).padStart(2, '0')}</span><h3>{selectedScene?.scene.title}</h3><p>{selectedScene?.scene.summary || 'No scene summary has been recorded.'}</p></div>
              <b>{formatDuration(selectedScene?.scene.duration_sec ?? 0)}</b>
            </div>
            <div className="phase-mini-timeline" aria-label="Selected scene shot timing">
              {selectedShots.map((row) => (
                <span
                  key={row.shot.id}
                  style={{ flexGrow: Math.max(1, Number(row.shot.duration_sec)) }}
                  title={`${row.code} · ${row.shot.duration_sec}s`}
                >
                  {row.code}
                </span>
              ))}
            </div>
            <div className="table-wrap phase-shot-table-wrap">
              <table className="phase-shot-table">
                <thead><tr><th>Shot</th><th>Purpose</th><th>Cast / location</th><th>Duration</th><th>Continuity</th></tr></thead>
                <tbody>
                  {selectedShots.map((row) => (
                    <tr key={row.shot.id}>
                      <td><b>{row.code}</b><small>{row.shot.title}</small></td>
                      <td>{row.shot.story_purpose || row.shot.visual_description || 'Not recorded'}</td>
                      <td>{row.shot.location || 'Location not mapped'}<small>{row.shot.characters?.length ?? 0} cast links</small></td>
                      <td>{Number(row.shot.duration_sec).toFixed(1)}s</td>
                      <td><span className="phase-evidence-pill">{row.shot.continuity_source_type.replaceAll('_', ' ')}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      ) : (
        <EmptyDesignState title="The segmentation workspace is ready" detail="No persisted chapters, scenes, or shots are available yet. The full Storyboard editor remains connected to the existing backend." />
      )}

      <div className="phase-preview-footer">
        <div><span>QA PREVIEW</span><b>Timing and coverage evidence</b><p>Calculated from current planning records—not a Phase 2 QA result.</p></div>
        <ul>
          <li><span>Duration alignment</span><b>{target && planned ? `${Math.abs(target - planned).toFixed(1)}s delta` : 'Not measured'}</b></li>
          <li><span>Model-safe duration</span><b>{shots.length ? `${shots.filter((row) => Number(row.shot.duration_sec) >= 6 && Number(row.shot.duration_sec) <= 10).length}/${shots.length} in 6–10s range` : 'Not measured'}</b></li>
          <li><span>Stable display codes</span><b>{shots.length ? `${shots.length} calculated previews` : 'Not measured'}</b></li>
        </ul>
        {onNavigate ? <button type="button" className="primary-button" onClick={() => onNavigate('storyboard')}>Edit in Storyboard</button> : null}
      </div>
    </div>
  )
}

function characterCompleteness(character: Character): number {
  const fields = [
    character.name,
    character.role,
    character.age_range,
    character.physical_description,
    character.personality,
    character.speaking_style,
    character.wardrobe,
    character.consistency_prompt,
    character.negative_identity_prompt,
  ]
  return Math.round((fields.filter(Boolean).length / fields.length) * 100)
}

function PhaseThreePreview({ phase, data, onNavigate }: PreviewProps) {
  const characters = useMemo(() => data?.characters ?? [], [data])
  const [selectedId, setSelectedId] = useState(characters[0]?.id ?? '')
  const selected = characters.find((item) => item.id === selectedId) ?? characters[0] ?? null
  const references = selected?.reference_assets ?? []
  const linkedShots = data?.chapters.flatMap((chapter) => chapter.scenes.flatMap((scene) =>
    scene.shots.filter((shot) => shot.characters?.some((link) => link.character_id === selected?.id)),
  )) ?? []

  return (
    <div className="phase-preview-workspace">
      <PhasePreviewHeader
        phase={phase}
        source="Live records"
        description="Build distinct, continuity-safe character identities and review the required nine-view reference plan before any media is produced."
        actions={[{ label: 'Open Characters', page: 'characters' }, { label: 'Open Voices', page: 'voices' }]}
        onNavigate={onNavigate}
      />
      <PreviewDisclosure />
      <div className="phase-workspace-metrics four">
        <WorkspaceMetric label="Characters" value={characters.length || '—'} />
        <WorkspaceMetric label="Principal cast" value={characters.filter((item) => (item.role || '').toLowerCase().includes('lead') || (item.reference_assets?.length ?? 0) > 0).length || '—'} />
        <WorkspaceMetric label="Reference links" value={characters.reduce((total, item) => total + (item.reference_assets?.length ?? 0), 0) || '—'} />
        <WorkspaceMetric label="Voice assignments" value={characters.filter((item) => item.assigned_voice_profile_id).length || '—'} detail={characters.length ? `${data?.voices.length ?? 0} voice profiles available` : undefined} />
      </div>

      {selected ? (
        <div className="phase-character-layout">
          <aside className="phase-character-list" aria-label="Character profiles">
            {characters.map((character) => (
              <button key={character.id} type="button" className={character.id === selected.id ? 'active' : ''} onClick={() => setSelectedId(character.id)}>
                <span>{initials(character.name)}</span>
                <div><b>{character.name}</b><small>{character.role || 'Role not recorded'}</small></div>
                <i>{characterCompleteness(character)}%</i>
              </button>
            ))}
          </aside>

          <section className="phase-character-profile">
            <div className="phase-character-hero">
              <div className="phase-character-avatar">
                {references[0]?.asset_id ? (
                  <ManagedAssetImage assetId={references[0].asset_id} alt={`${selected.name} reference`} fit="cover" errorLabel="Reference unavailable" />
                ) : <span>{initials(selected.name)}</span>}
              </div>
              <div><span>CHARACTER PROFILE</span><h3>{selected.name}</h3><p>{selected.role || 'Narrative role not recorded'} · {selected.age_range || 'Age range not recorded'}</p></div>
              <span className="phase-evidence-pill">{selected.approval_state}</span>
            </div>
            <div className="phase-character-facts">
              <article><span>Physical identity</span><p>{selected.physical_description || 'Add complexion, facial structure, eyes, hair, build, posture, and distinguishing traits.'}</p></article>
              <article><span>Personality & movement</span><p>{selected.personality || 'Add motivations, fears, emotional range, movement style, and habitual gestures.'}</p></article>
              <article><span>Voice & speech</span><p>{selected.speaking_style || 'Add speaking style, pace, energy, accent, and language direction.'}</p></article>
              <article><span>Wardrobe lock</span><p>{selected.wardrobe || 'Add canonical wardrobe, footwear, accessories, and permitted variants.'}</p></article>
            </div>
            <div className="phase-continuity-note"><span>CONTINUITY PROMPT</span><p>{selected.consistency_prompt || 'No continuity prompt has been stored.'}</p><small>{linkedShots.length} linked shots</small></div>
          </section>

          <section className="phase-nine-panel">
            <div className="phase-subheading"><div><span>NINE-PANEL SPECIFICATION</span><h3>Reference-view plan</h3><p>Each slot remains a planned requirement unless a real managed reference is linked.</p></div><b>{Math.min(9, references.length)}/9 linked</b></div>
            <div className="phase-nine-panel-grid">
              {NINE_PANEL_LABELS.map((label, index) => {
                const reference = references[index]
                return (
                  <article key={label}>
                    <div>{reference?.asset_id ? <ManagedAssetImage assetId={reference.asset_id} alt={`${selected.name} ${label}`} fit="cover" errorLabel="Reference unavailable" /> : <span>{index + 1}</span>}</div>
                    <b>{label}</b><small>{reference ? (reference.approved ? 'Approved reference' : 'Draft reference') : 'Planned view'}</small>
                  </article>
                )
              })}
            </div>
          </section>
        </div>
      ) : <EmptyDesignState title="The character workspace is ready" detail="No character records are available for this story yet. Profile fields and the nine-panel specification remain visible once the first character is added." />}

      <div className="phase-preview-footer compact">
        <div><span>PROFILE COVERAGE</span><b>Identity planning, not generated media</b><p>Completeness is calculated from stored profile fields and reference links.</p></div>
        {onNavigate ? <div className="phase-footer-actions"><button type="button" className="secondary-button" onClick={() => onNavigate('voices')}>Review voices</button><button type="button" className="primary-button" onClick={() => onNavigate('characters')}>Edit character profiles</button></div> : null}
      </div>
    </div>
  )
}

function PhaseFourPreview({ phase, data }: PreviewProps) {
  const scenes = useMemo(() => flattenScenes(data), [data])
  const shots = useMemo(() => flattenShots(scenes), [scenes])
  const locations = useMemo(() => {
    const values = new Map<string, ShotRow[]>()
    for (const row of shots) {
      const location = row.shot.location?.trim()
      if (!location) continue
      values.set(location, [...(values.get(location) ?? []), row])
    }
    return [...values.entries()].map(([name, locationShots]) => ({ name, shots: locationShots }))
  }, [shots])
  const [selectedLocation, setSelectedLocation] = useState(locations[0]?.name ?? '')
  const selected = locations.find((item) => item.name === selectedLocation) ?? locations[0] ?? null

  return (
    <div className="phase-preview-workspace">
      <PhasePreviewHeader
        phase={phase}
        source="Derived preview"
        description="Define reusable locations and story-critical assets, then trace geography, state, ownership, and continuity across every planned shot."
      />
      <PreviewDisclosure />
      <div className="phase-workspace-metrics four">
        <WorkspaceMetric label="Derived locations" value={locations.length || '—'} detail="From current shot records" />
        <WorkspaceMetric label="Location coverage" value={shots.length ? `${shots.filter((row) => row.shot.location).length}/${shots.length}` : '—'} detail="Shots with a location value" />
        <WorkspaceMetric label="Key-asset profiles" value="—" detail="Schema design pending" />
        <WorkspaceMetric label="Continuity states" value="—" detail="Workspace template" />
      </div>

      <div className="phase-location-layout">
        <section className="phase-location-catalog">
          <div className="phase-subheading"><div><span>LOCATION CATALOG</span><h3>Environment coverage</h3><p>Location names are derived from persisted shots; profile fields below are the intended UX.</p></div></div>
          {locations.length ? (
            <div className="phase-location-cards">
              {locations.map((location, index) => (
                <button key={location.name} type="button" className={location.name === selected?.name ? 'active' : ''} onClick={() => setSelectedLocation(location.name)}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <div><b>{location.name}</b><small>{location.shots.length} shots · first appears in {location.shots[0]?.sceneTitle}</small></div>
                  <i aria-hidden="true">›</i>
                </button>
              ))}
            </div>
          ) : <EmptyDesignState title="No location values are recorded" detail="The location profile design remains available without inventing production data." />}
        </section>

        <section className="phase-location-profile">
          <div className="phase-subheading"><div><span>LOCATION PROFILE</span><h3>{selected?.name || 'Select a location'}</h3><p>{selected ? `${selected.shots.length} shot uses are connected to this derived profile.` : 'No persisted location is selected.'}</p></div><span className="phase-evidence-pill">Derived</span></div>
          <div className="phase-profile-field-grid">
            {[
              ['Story purpose', selected?.shots[0]?.shot.story_purpose || 'Not recorded'],
              ['Geography & scale', 'Profile field ready for backend support'],
              ['Screen direction', 'Entrances, exits, landmarks, and camera access'],
              ['Light & weather', 'Time-of-day variants, palette, and material behavior'],
              ['Environmental sound', 'Ambience and recurring acoustic cues'],
              ['Forbidden drift', 'Geometry and landmark changes that must never occur'],
            ].map(([label, value]) => <article key={label}><span>{label}</span><p>{value}</p></article>)}
          </div>
        </section>
      </div>

      <section className="phase-key-assets-panel">
        <div className="phase-subheading"><div><span>KEY-ASSET REGISTRY</span><h3>Story-critical object continuity</h3><p>The current backend has no canonical location/key-asset model, so this complete UI structure stays truthful and unpopulated.</p></div><span className="phase-source-pill">Design template</span></div>
        <div className="phase-key-asset-grid">
          {[
            ['Identity', 'Canonical name, function, size, shape, material, color'],
            ['Condition', 'Age, wear, damage state, and allowed transformations'],
            ['Ownership', 'Owner, location, movement, and interaction rules'],
            ['Shot mapping', 'State per shot and continuity-change timeline'],
            ['References', 'Front, side, three-quarter, detail, and scale views'],
          ].map(([title, detail], index) => <article key={title}><span>{index + 1}</span><div><b>{title}</b><p>{detail}</p></div><small>Field group</small></article>)}
        </div>
      </section>
    </div>
  )
}

function PhaseFivePreview({ phase, data, onNavigate }: PreviewProps) {
  const scenes = useMemo(() => flattenScenes(data), [data])
  const shots = useMemo(() => flattenShots(scenes), [scenes])
  const [selectedShotId, setSelectedShotId] = useState(shots[0]?.shot.id ?? '')
  const [promptTab, setPromptTab] = useState<'image' | 'video' | 'negative'>('image')
  const selected = shots.find((item) => item.shot.id === selectedShotId) ?? shots[0] ?? null
  const promptCoverage = shots.filter((row) => row.shot.prompt_positive && row.shot.prompt_video && row.shot.prompt_negative).length
  const recommendationCoverage = shots.filter((row) => (row.shot.recommendations?.length ?? 0) > 0).length
  const promptText = selected ? {
    image: selected.shot.prompt_positive,
    video: selected.shot.prompt_video,
    negative: selected.shot.prompt_negative,
  }[promptTab] : null

  return (
    <div className="phase-preview-workspace">
      <PhasePreviewHeader
        phase={phase}
        source="Live records"
        description="Review every generation instruction, reference dependency, workflow recommendation, and technical setting before media production begins."
        actions={[{ label: 'Open Routing', page: 'routing' }, { label: 'Open Workflows', page: 'workflows' }]}
        onNavigate={onNavigate}
      />
      <PreviewDisclosure />
      <div className="phase-workspace-metrics five">
        <WorkspaceMetric label="Shot packages" value={shots.length ? `${promptCoverage}/${shots.length}` : '—'} detail="Image + video + negative" />
        <WorkspaceMetric label="Workflow routes" value={shots.length ? `${recommendationCoverage}/${shots.length}` : '—'} detail="Persisted recommendations" />
        <WorkspaceMetric label="Character prompts" value={data?.characters.length || '—'} detail="Profile-linked" />
        <WorkspaceMetric label="Voice packages" value={data?.voices.length || '—'} detail="Current profiles" />
        <WorkspaceMetric label="Target runtime" value={data ? formatDuration(data.story.target_duration_sec) : '—'} />
      </div>

      {selected ? (
        <div className="phase-prompt-layout">
          <aside className="phase-package-list" aria-label="Shot prompt packages">
            <div className="phase-subheading"><span>SHOT PACKAGES</span><b>{promptCoverage}/{shots.length} complete</b></div>
            {shots.map((row) => (
              <button key={row.shot.id} type="button" className={row.shot.id === selected.shot.id ? 'active' : ''} onClick={() => setSelectedShotId(row.shot.id)}>
                <span>{row.code}</span><div><b>{row.shot.title}</b><small>{row.sceneTitle}</small></div><i className={row.shot.prompt_positive ? 'has-record' : ''}>{row.shot.prompt_positive ? '●' : '○'}</i>
              </button>
            ))}
          </aside>
          <section className="phase-prompt-inspector">
            <div className="phase-subheading"><div><span>{selected.code} · PROMPT PACKAGE</span><h3>{selected.shot.title}</h3><p>{selected.shot.visual_description || selected.shot.story_purpose || 'No visual description has been recorded.'}</p></div><span className="phase-evidence-pill">{selected.shot.prompt_approval_state || 'draft'}</span></div>
            <div className="phase-inline-tabs" role="tablist" aria-label="Prompt type">
              {(['image', 'video', 'negative'] as const).map((tab) => <button key={tab} type="button" role="tab" aria-selected={promptTab === tab} className={promptTab === tab ? 'active' : ''} onClick={() => setPromptTab(tab)}>{tab} prompt</button>)}
            </div>
            <div className="phase-prompt-copy"><span>{promptTab.toUpperCase()} PROMPT</span><p>{promptText || `No ${promptTab} prompt has been stored for this shot.`}</p></div>
            <div className="phase-prompt-support-grid">
              <article><span>Continuity</span><p>{selected.shot.prompt_continuity_instructions || 'No continuity instructions recorded.'}</p></article>
              <article><span>Style lock</span><p>{selected.shot.prompt_style_lock || data?.story.visual_style || 'No style-lock prompt recorded.'}</p></article>
              <article><span>Camera</span><p>{selected.shot.camera_direction || 'No camera direction recorded.'}</p></article>
              <article><span>Motion</span><p>{selected.shot.motion_direction || 'No motion direction recorded.'}</p></article>
            </div>
          </section>
        </div>
      ) : <EmptyDesignState title="The prompt-package workspace is ready" detail="No persisted shots exist yet. The design will populate from current Storyboard records without creating media." />}

      <section className="phase-workflow-evidence">
        <div className="phase-subheading"><div><span>WORKFLOW EVIDENCE</span><h3>Recommendation states stay explicit</h3><p>Catalog visibility never implies that a workflow can execute.</p></div></div>
        <div className="phase-workflow-state-grid">
          {WORKFLOW_STATES.map(([label, detail]) => <article key={label}><span className={`workflow-state-dot ${label.toLowerCase().replaceAll(' ', '-')}`} /><div><b>{label}</b><p>{detail}</p></div></article>)}
        </div>
        {onNavigate ? <div className="phase-footer-actions"><button type="button" className="secondary-button" onClick={() => onNavigate('routing')}>Review model routing</button><button type="button" className="primary-button" onClick={() => onNavigate('workflows')}>Review workflow catalog</button></div> : null}
      </section>
    </div>
  )
}

function PhaseSixPreview({ phase, data, onNavigate }: PreviewProps) {
  const scenes = useMemo(() => flattenScenes(data), [data])
  const shots = useMemo(() => flattenShots(scenes), [scenes])
  const [mediaTab, setMediaTab] = useState<'images' | 'voices' | 'mapping'>('images')
  const requiredFrames = shots.filter((row) => row.shot.starting_image_required)
  const mappedFrames = requiredFrames.filter((row) => row.shot.starting_image_asset_id)
  const characterReferences = (data?.characters ?? []).reduce((total, character) => total + (character.reference_assets?.length ?? 0), 0)
  const voices = data?.voices ?? []
  const assignedVoices = data?.characters.filter((character) => character.assigned_voice_profile_id).length ?? 0

  return (
    <div className="phase-preview-workspace">
      <PhasePreviewHeader
        phase={phase}
        source="Live records"
        description="Review character references, location art direction, clean starting frames, voice profiles, and their shot-level mappings in one production dashboard."
        actions={[{ label: 'Open Starting Images', page: 'images' }, { label: 'Open Voices', page: 'voices' }]}
        onNavigate={onNavigate}
      />
      <PreviewDisclosure />
      <div className="phase-workspace-metrics five">
        <WorkspaceMetric label="Character refs" value={characterReferences || '—'} detail={`${data?.characters.length ?? 0} profiles`} />
        <WorkspaceMetric label="Starting frames" value={requiredFrames.length ? `${mappedFrames.length}/${requiredFrames.length}` : '—'} detail="Persisted mappings" />
        <WorkspaceMetric label="Voice profiles" value={voices.length || '—'} detail={`${assignedVoices} character assignments`} />
        <WorkspaceMetric label="Shot coverage" value={shots.length || '—'} />
        <WorkspaceMetric label="Video generated" value="No" detail="Phase boundary preserved" />
      </div>

      <div className="phase-inline-tabs phase-media-tabs" role="tablist" aria-label="Phase 6 media view">
        {(['images', 'voices', 'mapping'] as const).map((tab) => <button key={tab} type="button" role="tab" aria-selected={mediaTab === tab} className={mediaTab === tab ? 'active' : ''} onClick={() => setMediaTab(tab)}>{tab === 'images' ? 'Image assets' : tab === 'voices' ? 'Voice assets' : 'Shot mapping'}</button>)}
      </div>

      {mediaTab === 'images' ? (
        <div className="phase-media-layout">
          <section>
            <div className="phase-subheading"><div><span>STARTING-FRAME GALLERY</span><h3>Clean frame coverage</h3><p>Only real managed asset IDs render. Missing records remain clear placeholders.</p></div><b>{mappedFrames.length}/{requiredFrames.length || 0} mapped</b></div>
            {requiredFrames.length ? <div className="phase-start-frame-grid">
              {requiredFrames.slice(0, 12).map((row) => <article key={row.shot.id}><div>{row.shot.starting_image_asset_id ? <ManagedAssetImage assetId={row.shot.starting_image_asset_id} alt={`${row.code} starting frame`} fit="cover" errorLabel="Starting frame unavailable" /> : <span>{row.code}</span>}</div><b>{row.code} · {row.shot.title}</b><small>{row.shot.starting_image_asset_id ? 'Managed asset mapped' : 'Starting frame planned'}</small></article>)}
            </div> : <EmptyDesignState title="No starting-frame requirements are recorded" detail="The gallery will display managed assets as soon as shots declare a requirement." />}
          </section>
          <aside className="phase-media-summary">
            <span>CHARACTER MEDIA</span>
            <h3>Nine-view coverage</h3>
            <ul>{(data?.characters ?? []).map((character) => <li key={character.id}><span>{initials(character.name)}</span><div><b>{character.name}</b><small>{character.reference_assets?.length ?? 0}/9 linked views</small></div><i>{character.approval_state}</i></li>)}</ul>
          </aside>
        </div>
      ) : null}

      {mediaTab === 'voices' ? (
        <section className="phase-voice-board">
          <div className="phase-subheading"><div><span>VOICE & AUDIO BOARD</span><h3>Profiles, consent, and timing</h3><p>These are existing planning records; this view never requests synthesis or a provider preview.</p></div><b>{voices.length} profiles</b></div>
          {voices.length ? <div className="phase-voice-grid">{voices.map((voice) => <article key={voice.id}><div className="phase-audio-wave" aria-hidden="true"><i /><i /><i /><i /><i /><i /></div><span className="phase-evidence-pill">{voice.approval_state}</span><h4>{voice.name}</h4><p>{voice.tone || voice.design_description || voice.source_description || 'Voice direction has not been recorded.'}</p><dl><div><dt>Mode</dt><dd>{voice.setup_mode.replaceAll('_', ' ')}</dd></div><div><dt>Provider</dt><dd>{voice.provider || 'Not selected'}</dd></div><div><dt>Consent</dt><dd>{voice.consent_required ? (voice.consent_confirmed ? 'Confirmed' : 'Pending') : 'Not required'}</dd></div></dl></article>)}</div> : <EmptyDesignState title="No voice profiles are stored" detail="The Voice workspace remains connected to the existing provider-safe setup flow." />}
        </section>
      ) : null}

      {mediaTab === 'mapping' ? (
        <section className="phase-mapping-board">
          <div className="phase-subheading"><div><span>CANONICAL MAPPING</span><h3>Shot input manifest</h3><p>Every row connects current planning records without fabricating media provenance.</p></div></div>
          <div className="table-wrap"><table><thead><tr><th>Shot</th><th>Starting frame</th><th>Cast</th><th>Voice</th><th>Prompt</th></tr></thead><tbody>{shots.map((row) => <tr key={row.shot.id}><td><b>{row.code}</b><small>{row.shot.title}</small></td><td>{row.shot.starting_image_asset_id ? 'Mapped asset' : row.shot.starting_image_required ? 'Planned' : 'Not required'}</td><td>{row.shot.characters?.length ?? 0} links</td><td>{row.shot.narration_voice_profile_id ? 'Mapped' : row.shot.narration ? 'Profile needed' : 'No speech'}</td><td>{row.shot.prompt_positive && row.shot.prompt_video ? 'Package present' : 'Incomplete'}</td></tr>)}</tbody></table></div>
        </section>
      ) : null}

      {onNavigate ? <div className="phase-preview-footer compact"><div><span>CONNECTED WORKSPACES</span><b>Review and edit the live records</b><p>These actions navigate to existing backend-connected editors.</p></div><div className="phase-footer-actions"><button type="button" className="secondary-button" onClick={() => onNavigate('characters')}>Character references</button><button type="button" className="secondary-button" onClick={() => onNavigate('voices')}>Voice profiles</button><button type="button" className="primary-button" onClick={() => onNavigate('images')}>Starting images</button></div></div> : null}
    </div>
  )
}

function PhaseSevenPreview({ phase, data, onNavigate }: PreviewProps) {
  const scenes = useMemo(() => flattenScenes(data), [data])
  const shots = useMemo(() => flattenShots(scenes), [scenes])
  const planned = shots.reduce((total, row) => total + Number(row.shot.duration_sec), 0)
  const [assemblyTab, setAssemblyTab] = useState<'timeline' | 'review' | 'manifest'>('timeline')

  return (
    <div className="phase-preview-workspace">
      <PhasePreviewHeader
        phase={phase}
        source="Design template"
        description="Review the intended candidate-selection, assembly, audio, subtitle, technical-QA, and provenance experience without presenting ungenerated clips as finished work."
        actions={[{ label: 'Open Workflows', page: 'workflows' }, { label: 'Open Exports', page: 'exports' }]}
        onNavigate={onNavigate}
      />
      <PreviewDisclosure />
      <div className="phase-workspace-metrics five">
        <WorkspaceMetric label="Planned shots" value={shots.length || '—'} />
        <WorkspaceMetric label="Assembly runtime" value={planned ? formatDuration(planned) : '—'} detail={data ? `${formatDuration(data.story.target_duration_sec)} target` : undefined} />
        <WorkspaceMetric label="Selected clips" value="—" detail="No project-scoped clip API" />
        <WorkspaceMetric label="Final output" value="Not produced" />
        <WorkspaceMetric label="Final QA" value="Not evaluated" />
      </div>

      <div className="phase-inline-tabs phase-assembly-tabs" role="tablist" aria-label="Phase 7 assembly view">
        {(['timeline', 'review', 'manifest'] as const).map((tab) => <button key={tab} type="button" role="tab" aria-selected={assemblyTab === tab} className={assemblyTab === tab ? 'active' : ''} onClick={() => setAssemblyTab(tab)}>{tab === 'timeline' ? 'Assembly timeline' : tab === 'review' ? 'Final QA review' : 'Manifest & provenance'}</button>)}
      </div>

      {assemblyTab === 'timeline' ? (
        <div className="phase-assembly-layout">
          <section className="phase-preview-monitor">
            <div className="phase-monitor-screen"><span aria-hidden="true">▶</span><div><b>Final preview area</b><p>No project-scoped video output is available.</p></div></div>
            <div className="phase-monitor-controls"><span>00:00:00</span><div><i /></div><span>{formatDuration(planned || data?.story.target_duration_sec || 0)}</span></div>
          </section>
          <section className="phase-assembly-timeline">
            <div className="phase-subheading"><div><span>ASSEMBLY TIMELINE</span><h3>Shot, dialogue, music, and subtitle tracks</h3><p>Timeline geometry is derived from planned shot durations only.</p></div></div>
            <div className="assembly-track"><b>VIDEO</b><div>{shots.map((row) => <span key={row.shot.id} style={{ flexGrow: Math.max(1, Number(row.shot.duration_sec)) }} title={`${row.code} · clip not generated`}>{row.code}</span>)}</div></div>
            <div className="assembly-track audio"><b>VOICE</b><div>{shots.filter((row) => row.shot.narration).map((row) => <span key={row.shot.id} style={{ flexGrow: Math.max(1, Number(row.shot.duration_sec)) }}>{row.code}</span>)}</div></div>
            <div className="assembly-track empty"><b>MUSIC</b><div><span>Music and SFX design lane</span></div></div>
            <div className="assembly-track empty"><b>CAPTIONS</b><div><span>Subtitle and accessibility lane</span></div></div>
          </section>
        </div>
      ) : null}

      {assemblyTab === 'review' ? (
        <section className="phase-final-qa">
          <div className="phase-subheading"><div><span>FINAL QA REVIEW</span><h3>Technical and creative validation</h3><p>Every check remains pending until real project-scoped outputs and probe evidence exist.</p></div><span className="phase-source-pill">Not evaluated</span></div>
          <div className="phase-final-qa-grid">
            {[
              ['Timeline coverage', 'Every planned shot has a selected, decodable clip.'],
              ['Continuity', 'Characters, locations, props, and transitions remain coherent.'],
              ['Motion quality', 'No black frames, frozen clips, severe flicker, or unacceptable blur.'],
              ['Audio sync', 'Narration and dialogue align with picture and remain intelligible.'],
              ['Delivery profile', 'Duration, aspect ratio, resolution, FPS, and 2× upscale are verified.'],
              ['Output integrity', 'Final decode, SHA-256, manifest, and provenance are stored.'],
            ].map(([title, detail]) => <article key={title}><span>○</span><div><b>{title}</b><p>{detail}</p></div><small>Pending evidence</small></article>)}
          </div>
        </section>
      ) : null}

      {assemblyTab === 'manifest' ? (
        <section className="phase-manifest-preview">
          <div className="phase-subheading"><div><span>FINAL MANIFEST</span><h3>Provenance and delivery record</h3><p>This schema preview does not claim that an output exists.</p></div><span className="phase-source-pill">Template</span></div>
          <div className="phase-manifest-grid">
            {[
              ['Output identity', 'Canonical filename, delivery path, SHA-256'],
              ['Picture profile', 'Codec, resolution, aspect ratio, FPS, frame count'],
              ['Audio profile', 'Codec, channels, sample rate, loudness, duration'],
              ['Source lineage', 'Selected clips, prompts, models, workflows, seeds'],
              ['Post-production', 'Upscale, interpolation, normalization, subtitles'],
              ['Review history', 'Candidate decisions, retries, QA reports, approvals'],
            ].map(([title, detail]) => <article key={title}><span>{title}</span><p>{detail}</p><code>Awaiting production output</code></article>)}
          </div>
        </section>
      ) : null}

      <div className="phase-preview-footer compact">
        <div><span>BACKEND PRESERVED</span><b>Execution remains separate from this design</b><p>No project-scoped clip, FFmpeg, or final-output API is currently represented as complete.</p></div>
        {onNavigate ? <div className="phase-footer-actions"><button type="button" className="secondary-button" onClick={() => onNavigate('workflows')}>Review workflows</button><button type="button" className="primary-button" onClick={() => onNavigate('exports')}>Open Exports</button></div> : null}
      </div>
    </div>
  )
}

export function ProductionPhasePreview(props: PreviewProps) {
  switch (props.phase.phase_number) {
    case 2:
      return <PhaseTwoPreview {...props} />
    case 3:
      return <PhaseThreePreview {...props} />
    case 4:
      return <PhaseFourPreview {...props} />
    case 5:
      return <PhaseFivePreview {...props} />
    case 6:
      return <PhaseSixPreview {...props} />
    case 7:
      return <PhaseSevenPreview {...props} />
    default:
      return null
  }
}
