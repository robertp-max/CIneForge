import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, type ProductionPipeline } from '../../api/client'
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

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ProductionPhases', () => {
  it('shows exactly seven phases, completed Phase 1, QA, and locked later phases', async () => {
    vi.mocked(api.getProductionPipeline).mockResolvedValue(pipeline)

    render(<ProductionPhases storyId="story-1" />)

    expect(await screen.findByText('Your complete script is ready for review.')).toBeTruthy()
    expect(screen.getByText('7 phases · no eighth phase')).toBeTruthy()
    expect(screen.getByText('All blocking checks passed')).toBeTruthy()
    expect(screen.getByText('The Test Film')).toBeTruthy()
    for (const name of phaseNames) expect(screen.getByText(new RegExp(name))).toBeTruthy()
    expect(screen.getAllByText(/Locked · not started/i)).toHaveLength(6)
  })

  it('saves edits as a new version and reruns QA', async () => {
    vi.mocked(api.getProductionPipeline).mockResolvedValue(pipeline)
    vi.mocked(api.revisePhaseOne).mockResolvedValue({
      pipeline,
      phase: pipeline.phases[0],
      completion_message: 'Your complete script is ready for review.',
    })
    render(<ProductionPhases storyId="story-1" />)
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
