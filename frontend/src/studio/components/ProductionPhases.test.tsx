import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, type ProductionPipeline, type StoryboardAggregate } from '../../api/client'
import { ProductionPhases } from './ProductionPhases'

vi.mock('../../api/client', () => ({
  api: {
    getProductionPipeline: vi.fn(),
    revisePhaseOne: vi.fn(),
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
    current_version_number: index === 0 ? 1 : null,
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

describe('ProductionPhases', () => {
  it('shows exactly seven enabled phase tabs and opens every UI workspace', async () => {
    vi.mocked(api.getProductionPipeline).mockResolvedValue(pipeline)

    render(<ProductionPhases storyId="story-1" data={aggregate} />)

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
    render(<ProductionPhases storyId="story-1" data={aggregate} />)

    const first = await screen.findByRole('tab', { name: /Script and Narrative Development/ })
    fireEvent.keyDown(first, { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: /Scene and Shot Segmentation/ }).getAttribute('aria-selected')).toBe('true')

    fireEvent.keyDown(screen.getByRole('tab', { name: /Scene and Shot Segmentation/ }), { key: 'End' })
    expect(screen.getByRole('tab', { name: /Video Generation, Assembly, and Final QA/ }).getAttribute('aria-selected')).toBe('true')

    fireEvent.keyDown(screen.getByRole('tab', { name: /Video Generation, Assembly, and Final QA/ }), { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: /Script and Narrative Development/ }).getAttribute('aria-selected')).toBe('true')
  })

  it('saves edits as a new version and reruns QA', async () => {
    vi.mocked(api.getProductionPipeline).mockResolvedValue(pipeline)
    vi.mocked(api.revisePhaseOne).mockResolvedValue({
      pipeline,
      phase: pipeline.phases[0],
      completion_message: 'Your complete script is ready for review.',
    })
    render(<ProductionPhases storyId="story-1" data={aggregate} />)
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
})
