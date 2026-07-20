import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, type ProductionPipeline, type StoryboardAggregate } from '../../api/client'
import { ProductionPhases } from './ProductionPhases'

vi.mock('../../api/client', () => ({
  api: {
    getProductionPipeline: vi.fn(),
    revisePhaseOne: vi.fn(),
    listPhaseVersions: vi.fn(),
    getPhaseVersion: vi.fn(),
    createPhaseVersion: vi.fn(),
    exportPhaseHistory: vi.fn(),
  },
}))

const phaseNames = [
  'Script and Narrative Development',
  'Scene and Shot Segmentation',
  'Character Development',
  'Location and Key-Asset Development',
  'Production Prompt and Workflow Package',
  'Image and Voice Generation and Mapping',
  'Video Generation, Assembly, and Final QA',
]

const packageData = {
  schema_name: 'cineforge.phase_one_script_package',
  schema_version: 1,
  project_title: 'The Test Film',
  logline: 'A complete test logline.',
  short_synopsis: 'A complete synopsis.',
  detailed_treatment: 'Opening, development, climax, and resolution.',
  complete_script: '## Opening\n**ACTION:** The story begins.\n**NARRATION:** The story begins.',
  narration_script: 'The story begins.',
  dialogue_script: 'No spoken character dialogue is required by the supplied source.',
  non_dialogue_action: ['The story begins.'],
  silent_visual_beats: ['The moment settles.'],
  emotional_progression: ['Orientation', 'Development', 'Climax', 'Resolution'],
  dramatic_escalation: ['Opening', 'Development', 'Climax', 'Resolution'],
  narrative_structure: { opening: 'A', middle: 'B', climax: 'C', resolution: 'D' },
  pacing_plan: [],
  duration_analysis: {
    target_duration_sec: 300,
    narration_word_count: 10,
    dialogue_word_count: 0,
    narration_duration_sec: 120,
    dialogue_duration_sec: 0,
    planned_silence_visual_duration_sec: 180,
    estimated_total_duration_sec: 300,
  },
  script_word_count: 640,
  source_fidelity_notes: ['All events retain source anchors.'],
  creative_assumptions: ['No unsupported event was added.'],
  creative_direction: { language: 'English' },
  generation_boundary: {
    phase: 1 as const,
    text_only: true as const,
    media_generated: false as const,
    rendering_enabled: false as const,
    final_scene_or_shot_segmentation_created: false as const,
  },
}

const pipeline: ProductionPipeline = {
  story_id: 'story-1',
  project_id: 'project-1',
  exact_phase_count: 7,
  completion_message: 'Your complete script is ready for review.',
  phases: phaseNames.map((name, index) => ({
    id: `phase-${index + 1}`,
    phase_number: index + 1,
    name,
    lifecycle_state: index === 0 ? 'ready_for_review' : 'not_started',
    current_version_number: index === 0 ? 1 : 1,
    version_count: 1,
    is_locked: index !== 0,
    locked_reason: index === 0 ? null : `Phase ${index} must be approved.`,
    is_stale: false,
    stale_reason: null,
    generation_completed_at: index === 0 ? '2026-07-19T00:00:00Z' : null,
    approved_at: null,
    latest_version: index === 0 ? {
      id: 'version-1',
      version_number: 1,
      lifecycle_state: 'ready_for_review',
      completed: true,
      input_snapshot_json: {},
      output_json: packageData,
      input_hash: 'a'.repeat(64),
      output_hash: 'b'.repeat(64),
      created_by: 'test',
      previous_version_id: null,
      created_at: '2026-07-19T00:00:00Z',
      updated_at: '2026-07-19T00:00:00Z',
    } : null,
    latest_qa_report: index === 0 ? {
      id: 'qa-1',
      entity_type: 'production_phase_version',
      entity_id: 'version-1',
      created_at: '2026-07-19T00:00:00Z',
      report_json: {
        phase_number: 1,
        passed: true,
        result: 'pass',
        checks: [{ code: 'phase_boundary', label: 'No downstream execution', passed: true, blocking: true, detail: 'Text only.' }],
        blocking_failures: [],
        review_items: [],
        phase_boundary: { images_generated: false, voices_generated: false, videos_generated: false },
      },
    } : null,
  })),
}

const aggregate: StoryboardAggregate = {
  revision: 'workspace-v1',
  content_hash: 'workspace-hash',
  planned_duration_sec: 15,
  discrepancy_sec: -285,
  story: {
    id: 'story-1',
    project_id: 'project-1',
    title: 'The Test Film',
    base_story: 'A complete source story.',
    target_duration_sec: 300,
    logline: 'A complete test logline.',
    synopsis: 'A complete synopsis.',
    audience: 'General audiences',
    tone: 'Reverent',
    genre: 'Cinematic narrative',
    visual_style: 'Grounded cinematic realism',
    point_of_view: 'Third person',
    production_notes: null,
    approval_state: 'draft',
  },
  chapters: [{
    id: 'chapter-1',
    order_index: 0,
    title: 'Act I',
    summary: 'The opening movement.',
    duration_sec: 15,
    scenes: [{
      id: 'scene-1',
      order_index: 0,
      title: 'Opening scene',
      summary: 'The story opens.',
      duration_sec: 15,
      shots: [{
        id: 'shot-1',
        order_index: 0,
        display_label: 'A',
        title: 'Opening image',
        duration_sec: 8,
        duration_override_reason: null,
        visual_description: 'A grounded opening frame.',
        story_purpose: 'Establish the world.',
        location: 'Primary location',
        continuity_source_type: 'none',
        approval_state: 'draft',
        production_status: 'planned',
        blocked_reason: null,
        continuity_source_shot_id: null,
        starting_image_required: true,
        starting_image_asset_id: null,
        narration: 'The story begins.',
        narration_voice_profile_id: 'voice-1',
        prompt_positive: 'Grounded cinematic opening image.',
        prompt_video: 'A slow, controlled camera move.',
        prompt_negative: 'flicker, identity drift',
        prompt_continuity_instructions: 'Preserve geography and screen direction.',
        prompt_style_lock: 'Grounded cinematic realism.',
        prompt_approval_state: 'draft',
        camera_direction: 'Wide establishing shot',
        motion_direction: 'Slow push in',
        characters: [{ character_id: 'character-1', role_in_shot: 'lead', order_index: 0, continuity_notes: null }],
        recommendations: [],
      }],
    }],
  }],
  characters: [{
    id: 'character-1',
    story_id: 'story-1',
    name: 'Lead Character',
    role: 'Lead',
    approval_state: 'draft',
    age_range: 'Adult',
    physical_description: 'Distinct, grounded appearance.',
    personality: 'Reflective and courageous',
    speaking_style: 'Measured',
    wardrobe: 'Continuity-locked wardrobe',
    consistency_prompt: 'Preserve identity and wardrobe.',
    negative_identity_prompt: 'identity drift',
    assigned_voice_profile_id: 'voice-1',
    reference_assets: [],
  }],
  voices: [{
    id: 'voice-1',
    story_id: 'story-1',
    character_id: 'character-1',
    name: 'Lead voice',
    setup_mode: 'manual',
    source_type: 'manual',
    consent_confirmed: false,
    consent_required: false,
    approval_state: 'draft',
    language: 'English',
    tone: 'Measured and warm',
  }],
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const baselineVersions = (phaseNumber: number) => [{
  id: `baseline-${phaseNumber}`,
  version_number: 1,
  label: 'Baseline',
  notes: 'Initial retained state for this phase.',
  source: 'baseline' as const,
  lifecycle_state: 'not_started' as const,
  completed: false,
  snapshot_schema_version: 1,
  input_hash: 'c'.repeat(64),
  output_hash: 'd'.repeat(64),
  created_by: 'system:baseline',
  previous_version_id: null,
  created_at: '2026-07-19T00:00:00Z',
  updated_at: '2026-07-19T00:00:00Z',
}]

function mockHistoryApis() {
  vi.mocked(api.listPhaseVersions).mockImplementation(async (_storyId, phaseNumber) => baselineVersions(phaseNumber))
  vi.mocked(api.getPhaseVersion).mockImplementation(async (storyId, phaseNumber, versionId) => ({
    ...baselineVersions(phaseNumber)[0],
    id: versionId,
    story_id: storyId,
    project_id: 'project-1',
    phase_number: phaseNumber,
    phase_name: phaseNames[phaseNumber - 1],
    input_snapshot_json: {},
    output_json: { schema_name: 'cineforge.production_phase_snapshot', phase_number: phaseNumber },
    verified: true,
  }))
  vi.mocked(api.createPhaseVersion).mockResolvedValue({
    version: {
      ...baselineVersions(1)[0],
      id: 'manual-1',
      version_number: 2,
      label: 'Director review',
      source: 'manual',
      story_id: 'story-1',
      project_id: 'project-1',
      phase_number: 1,
      phase_name: phaseNames[0],
      input_snapshot_json: {},
      output_json: {},
      verified: true,
    },
    pipeline,
  })
  vi.mocked(api.exportPhaseHistory).mockResolvedValue({
    schema_name: 'cineforge.phase-history',
    version: 1,
    project_id: 'project-1',
    story_id: 'story-1',
    exported_at: '2026-07-19T00:00:00Z',
    integrity: {
      verified: true,
      iteration_count: 7,
      snapshot_count: 7,
      phase_counts: { '1': 1, '2': 1, '3': 1, '4': 1, '5': 1, '6': 1, '7': 1 },
      hashes: Array.from({ length: 7 }, () => 'e'.repeat(64)),
    },
    iterations: [],
  })
}

describe('ProductionPhases', () => {
  it('shows exactly seven enabled phase tabs and opens every UI workspace', async () => {
    vi.mocked(api.getProductionPipeline).mockResolvedValue(pipeline)
    mockHistoryApis()

    render(<ProductionPhases storyId="story-1" projectId="project-1" data={aggregate} />)

    expect(await screen.findByText('Your complete script is ready for review.')).toBeTruthy()
    expect(screen.getByText('7 complete workspaces')).toBeTruthy()
    expect(screen.getByText('All blocking checks passed')).toBeTruthy()
    expect(screen.getByText('The Test Film')).toBeTruthy()
    const tabs = screen.getAllByRole('tab')
    expect(tabs).toHaveLength(7)
    tabs.forEach((tab) => expect(tab.hasAttribute('disabled')).toBe(false))
    expect(screen.queryByText(/Locked ·/i)).toBeNull()

    for (const name of phaseNames.slice(1)) {
      fireEvent.click(screen.getByRole('tab', { name: new RegExp(name) }))
      expect(screen.getByRole('heading', { name })).toBeTruthy()
      expect(screen.getByText('Interactive UI/UX preview')).toBeTruthy()
    }

    fireEvent.click(screen.getByRole('tab', { name: /Script and Narrative Development/ }))
    expect(screen.getByText('The Test Film')).toBeTruthy()
    expect(api.getProductionPipeline).toHaveBeenCalledTimes(1)
    expect(api.revisePhaseOne).not.toHaveBeenCalled()
  })

  it('supports keyboard navigation across the seven phase tabs', async () => {
    vi.mocked(api.getProductionPipeline).mockResolvedValue(pipeline)
    mockHistoryApis()
    render(<ProductionPhases storyId="story-1" projectId="project-1" data={aggregate} />)

    const first = await screen.findByRole('tab', { name: /Script and Narrative Development/ })
    fireEvent.keyDown(first, { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: /Scene and Shot Segmentation/ }).getAttribute('aria-selected')).toBe('true')

    fireEvent.keyDown(screen.getByRole('tab', { name: /Scene and Shot Segmentation/ }), { key: 'End' })
    expect(screen.getByRole('tab', { name: /Video Generation, Assembly, and Final QA/ }).getAttribute('aria-selected')).toBe('true')

    fireEvent.keyDown(screen.getByRole('tab', { name: /Video Generation, Assembly, and Final QA/ }), { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: /Script and Narrative Development/ }).getAttribute('aria-selected')).toBe('true')
  })

  it('renders Phase 2 segmentation workspace from live planning records', async () => {
    const onNavigate = vi.fn()
    vi.mocked(api.getProductionPipeline).mockResolvedValue(pipeline)
    mockHistoryApis()
    render(
      <ProductionPhases
        storyId="story-1"
        projectId="project-1"
        data={aggregate}
        onNavigate={onNavigate}
      />,
    )

    fireEvent.click(await screen.findByRole('tab', { name: /Scene and Shot Segmentation/ }))

    expect(screen.getByRole('heading', { name: 'Scene and Shot Segmentation' })).toBeTruthy()
    expect(screen.getByText('Interactive UI/UX preview')).toBeTruthy()
    expect(screen.getByText('Chapters / acts')).toBeTruthy()
    expect(screen.getByText('STRUCTURE')).toBeTruthy()
    expect(screen.getByLabelText('Scene browser')).toBeTruthy()
    expect(screen.getByRole('button', { name: /Opening scene/i })).toBeTruthy()
    expect(screen.getByLabelText('Selected scene shot timing')).toBeTruthy()
    expect(screen.getAllByText('S01A').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('Establish the world.')).toBeTruthy()
    expect(screen.getByText('Primary location')).toBeTruthy()
    expect(screen.getByText('8.0s')).toBeTruthy()
    expect(screen.getByText('None')).toBeTruthy()
    expect(screen.getByText(/PLANNING DIAGNOSTICS|QA PREVIEW/)).toBeTruthy()
    expect(screen.getByText(/1\/1 shots in 6–10s/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Edit in Storyboard' }))
    expect(onNavigate).toHaveBeenCalledWith('storyboard')
    expect(screen.queryByText(/Locked/i)).toBeNull()
  })

  it('saves edits as a new version and reruns QA', async () => {
    vi.mocked(api.getProductionPipeline).mockResolvedValue(pipeline)
    mockHistoryApis()
    vi.mocked(api.revisePhaseOne).mockResolvedValue({
      pipeline,
      phase: pipeline.phases[0],
      completion_message: 'Your complete script is ready for review.',
    })
    render(<ProductionPhases storyId="story-1" projectId="project-1" data={aggregate} />)
    await screen.findByText('The Test Film')

    fireEvent.click(screen.getByRole('button', { name: 'Edit script package' }))
    fireEvent.change(screen.getByLabelText('Logline'), { target: { value: 'A revised logline.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save as new version & rerun QA' }))

    await waitFor(() => expect(api.revisePhaseOne).toHaveBeenCalledTimes(1))
    expect(api.revisePhaseOne).toHaveBeenCalledWith('story-1', expect.objectContaining({
      expected_version_number: 1,
      logline: 'A revised logline.',
    }))
  })

  it('loads SQLite-backed history and retains a current draft iteration', async () => {
    vi.mocked(api.getProductionPipeline).mockResolvedValue(pipeline)
    mockHistoryApis()
    render(<ProductionPhases storyId="story-1" projectId="project-1" data={aggregate} />)
    await screen.findByText('Current working draft')

    fireEvent.click(screen.getByRole('button', { name: 'New iteration' }))
    fireEvent.change(screen.getByPlaceholderText(/Director review/), { target: { value: 'Director review' } })
    fireEvent.click(screen.getByRole('button', { name: 'Retain current draft' }))

    await waitFor(() => expect(api.createPhaseVersion).toHaveBeenCalledTimes(1))
    expect(api.createPhaseVersion).toHaveBeenCalledWith(
      'story-1',
      1,
      expect.objectContaining({ label: 'Director review' }),
    )
    expect(api.listPhaseVersions).toHaveBeenCalled()
  })

  it('resolves packageData from history when the pipeline head is a non-package snapshot', async () => {
    const buriedPipeline: ProductionPipeline = {
      ...pipeline,
      phases: pipeline.phases.map((phase, index) => (
        index === 0
          ? {
              ...phase,
              current_version_number: 2,
              version_count: 2,
              latest_version: {
                id: 'snapshot-head',
                version_number: 2,
                lifecycle_state: 'ready_for_review',
                completed: false,
                input_snapshot_json: { reason: 'manual_retain' },
                output_json: {
                  schema_name: 'cineforge.production_phase_snapshot',
                  phase_number: 1,
                  narrative: { title: 'Not the package' },
                },
                input_hash: 'f'.repeat(64),
                output_hash: '0'.repeat(64),
                created_by: 'tester',
                previous_version_id: 'version-1',
                created_at: '2026-07-19T01:00:00Z',
                updated_at: '2026-07-19T01:00:00Z',
              },
            }
          : phase
      )),
    }
    vi.mocked(api.getProductionPipeline).mockResolvedValue(buriedPipeline)
    vi.mocked(api.listPhaseVersions).mockImplementation(async (_storyId, phaseNumber) => {
      if (phaseNumber !== 1) return baselineVersions(phaseNumber)
      return [
        {
          id: 'version-1',
          version_number: 1,
          label: 'Generated package',
          notes: '',
          source: 'generated' as const,
          lifecycle_state: 'ready_for_review' as const,
          completed: true,
          snapshot_schema_version: 1,
          input_hash: 'a'.repeat(64),
          output_hash: 'b'.repeat(64),
          created_by: 'test',
          previous_version_id: null,
          created_at: '2026-07-19T00:00:00Z',
          updated_at: '2026-07-19T00:00:00Z',
        },
        {
          id: 'snapshot-head',
          version_number: 2,
          label: 'Director review',
          notes: '',
          source: 'manual' as const,
          lifecycle_state: 'ready_for_review' as const,
          completed: false,
          snapshot_schema_version: 1,
          input_hash: 'f'.repeat(64),
          output_hash: '0'.repeat(64),
          created_by: 'tester',
          previous_version_id: 'version-1',
          created_at: '2026-07-19T01:00:00Z',
          updated_at: '2026-07-19T01:00:00Z',
        },
      ]
    })
    vi.mocked(api.getPhaseVersion).mockImplementation(async (storyId, phaseNumber, versionId) => {
      if (versionId === 'version-1') {
        return {
          id: 'version-1',
          version_number: 1,
          label: 'Generated package',
          notes: '',
          source: 'generated',
          lifecycle_state: 'ready_for_review',
          completed: true,
          snapshot_schema_version: 1,
          input_hash: 'a'.repeat(64),
          output_hash: 'b'.repeat(64),
          created_by: 'test',
          previous_version_id: null,
          created_at: '2026-07-19T00:00:00Z',
          updated_at: '2026-07-19T00:00:00Z',
          story_id: storyId,
          project_id: 'project-1',
          phase_number: phaseNumber,
          phase_name: phaseNames[0],
          input_snapshot_json: {},
          output_json: packageData,
          verified: true,
        }
      }
      return {
        ...baselineVersions(phaseNumber)[0],
        id: versionId,
        story_id: storyId,
        project_id: 'project-1',
        phase_number: phaseNumber,
        phase_name: phaseNames[phaseNumber - 1],
        input_snapshot_json: {},
        output_json: { schema_name: 'cineforge.production_phase_snapshot', phase_number: phaseNumber },
        verified: true,
      }
    })

    render(<ProductionPhases storyId="story-1" projectId="project-1" data={aggregate} />)

    expect(await screen.findByText('The Test Film')).toBeTruthy()
    expect(screen.getByText('Complete script package')).toBeTruthy()
    expect(screen.getByText('A complete test logline.')).toBeTruthy()
    expect(screen.queryByText('Phase 1 has not started')).toBeNull()
  })

  it('renders Phase 7 assembly workspace with timeline, QA, and manifest tabs', async () => {
    const onNavigate = vi.fn()
    vi.mocked(api.getProductionPipeline).mockResolvedValue(pipeline)
    mockHistoryApis()
    render(
      <ProductionPhases
        storyId="story-1"
        projectId="project-1"
        data={aggregate}
        onNavigate={onNavigate}
      />,
    )

    fireEvent.click(await screen.findByRole('tab', { name: /Video Generation, Assembly, and Final QA/ }))

    expect(screen.getByRole('heading', { name: 'Video Generation, Assembly, and Final QA' })).toBeTruthy()
    expect(screen.getByText('Interactive UI/UX preview')).toBeTruthy()
    expect(screen.getByText('Planned shots')).toBeTruthy()
    expect(screen.getByText('Selected clips')).toBeTruthy()
    expect(screen.getByText('No project-scoped clip API')).toBeTruthy()
    expect(screen.getByText('Not produced')).toBeTruthy()
    expect(screen.getByText('not evaluated')).toBeTruthy()

    expect(screen.getByRole('tablist', { name: 'Phase 7 assembly view' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Assembly timeline' }).getAttribute('aria-selected')).toBe('true')
    expect(screen.getByLabelText('Final assembly preview')).toBeTruthy()
    expect(screen.getByText('Final preview area')).toBeTruthy()
    expect(screen.getByText(/No project-scoped video output is available/)).toBeTruthy()
    expect(screen.getByLabelText('Assembly timeline tracks')).toBeTruthy()
    expect(screen.getByText('ASSEMBLY TIMELINE')).toBeTruthy()
    expect(screen.getByText(/Clips are not generated or concatenated here/)).toBeTruthy()
    expect(screen.getByLabelText('Video clips by planned duration')).toBeTruthy()
    expect(screen.getAllByText('S01A').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Music and SFX design lane')).toBeTruthy()
    expect(screen.getByText('Subtitle and accessibility lane')).toBeTruthy()

    fireEvent.click(screen.getByRole('tab', { name: 'Final QA review' }))
    expect(screen.getByLabelText('Final QA review')).toBeTruthy()
    expect(screen.getByText('FINAL QA REVIEW')).toBeTruthy()
    expect(screen.getByText('Timeline coverage')).toBeTruthy()
    expect(screen.getByText('Output integrity')).toBeTruthy()
    expect(screen.getAllByText('Pending evidence').length).toBe(6)
    expect(screen.getByText(/No FFmpeg or decode validation is run from this UI/)).toBeTruthy()

    fireEvent.click(screen.getByRole('tab', { name: 'Manifest & provenance' }))
    expect(screen.getByLabelText('Final manifest and provenance')).toBeTruthy()
    expect(screen.getByText('FINAL MANIFEST')).toBeTruthy()
    expect(screen.getByText('Output identity')).toBeTruthy()
    expect(screen.getAllByText('Awaiting production output').length).toBe(6)
    expect(screen.getByText(/does not claim that an output exists/)).toBeTruthy()

    expect(screen.getByText('BACKEND PRESERVED')).toBeTruthy()
    expect(screen.getByText(/No project-scoped clip, FFmpeg, or final-output API/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Open Exports/i }))
    expect(onNavigate).toHaveBeenCalledWith('exports')
  })
})
