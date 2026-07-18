import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../api/client'
import { ImagesPage } from './ImagesPage'
import { useStudio } from '../StudioState'

vi.mock('../../api/client', () => ({
  api: {
    listStartingImageAssets: vi.fn(),
    listArtDirectionReferenceAssets: vi.fn(),
    updateStartingImageApproval: vi.fn(),
  },
  planningAssetContentUrl: (assetId: string) => `http://assets.test/${assetId}`,
}))

vi.mock('../StudioState', () => ({
  useStudio: vi.fn(),
}))

const startingAsset = {
  id: 'start-asset-1',
  project_id: 'project-1',
  kind: 'starting_image',
  source_type: 'imported',
  managed_uri: 'cineforge-planning://project-1/starting_image/frame.jpg',
  sha256: 'a'.repeat(64),
  mime_type: 'image/jpeg',
  width: 1792,
  height: 1008,
  duration_sec: null,
  approval_state: 'draft',
  metadata_json: {
    client: {
      classification: 'clean single-shot starting-image candidate',
      suggested_shot_code: 'S01A',
      confidence: 0.93,
      alternate_candidate_filenames: ['alternate.jpg'],
    },
  },
  original_filename: 'assigned-frame.jpg',
  size_bytes: 1234,
  archived_at: null,
  created_at: '2026-07-17T00:00:00Z',
  updated_at: '2026-07-17T00:00:00Z',
  is_duplicate: false,
}

const artAsset = {
  ...startingAsset,
  id: 'art-board-1',
  kind: 'art_direction_reference',
  original_filename: 'multi-panel-board.png',
  metadata_json: { client: { scene_number: 1 } },
}

const assignedShot = {
  id: 'shot-assigned',
  order_index: 0,
  title: 'S01A — Assigned',
  duration_sec: 7.5,
  duration_override_reason: null,
  visual_description: 'Assigned shot',
  story_purpose: 'Test',
  location: 'Summit',
  continuity_source_type: 'none',
  approval_state: 'draft',
  production_status: 'planned',
  blocked_reason: null,
  continuity_source_shot_id: null,
  starting_image_required: true,
  starting_image_asset_id: startingAsset.id,
  narration: null,
  prompt_positive: 'Prompt',
  prompt_video: null,
  prompt_negative: null,
  prompt_continuity_instructions: null,
  prompt_style_lock: null,
  recommendations: [],
}

const unassignedShot = {
  ...assignedShot,
  id: 'shot-unassigned',
  order_index: 1,
  title: 'S01B — Unassigned',
  starting_image_asset_id: null,
}

function studioValue(saveShot = vi.fn()) {
  return {
    data: {
      story: { id: 'story-1', project_id: 'project-1' },
      chapters: [
        {
          id: 'chapter-1',
          title: 'Chapter',
          scenes: [
            {
              id: 'scene-1',
              title: 'Scene',
              art_direction_reference_asset_ids: [artAsset.id],
              shots: [assignedShot, unassignedShot],
            },
          ],
        },
      ],
    },
    readiness: { reasons: [] },
    busy: false,
    saveShot,
    setMessage: vi.fn(),
  }
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ImagesPage managed starting-image truth', () => {
  it('shows assigned and unassigned truth, metadata, and excludes art boards from candidates', async () => {
    vi.mocked(useStudio).mockReturnValue(studioValue() as never)
    vi.mocked(api.listStartingImageAssets).mockResolvedValue({
      items: [startingAsset, artAsset],
      total: 2,
    } as never)
    vi.mocked(api.listArtDirectionReferenceAssets).mockResolvedValue({
      items: [artAsset],
      total: 1,
    } as never)

    render(<ImagesPage />)
    const assignedImage = await screen.findByAltText('Starting image for S01A — Assigned')

    const assignedCard = assignedImage.closest('article')
    const unassignedCard = screen.getByText('S01B — Unassigned').closest('article')
    expect(assignedCard?.textContent).toContain('assigned-frame.jpg')
    expect(assignedCard?.textContent).not.toContain('Missing')
    expect(unassignedCard?.textContent).toContain('No starting image assigned')
    expect(unassignedCard?.textContent).toContain('Missing')
    expect(screen.getByText('Reviewed alternates:').parentElement?.textContent).toContain('alternate.jpg')
    expect(screen.getByText('Mapping confidence').parentElement?.textContent).toContain('0.93')

    const candidateSelect = screen.getByLabelText('Candidate asset') as HTMLSelectElement
    expect(Array.from(candidateSelect.options).map((option) => option.textContent).join(' ')).not.toContain(
      'multi-panel-board.png',
    )
    expect(screen.getByAltText('Art-direction storyboard reference for Scene')).toBeTruthy()
  })

  it('shows a broken-reference fallback and clears through persisted shot state', async () => {
    const saveShot = vi.fn().mockResolvedValue(undefined)
    vi.mocked(useStudio).mockReturnValue(studioValue(saveShot) as never)
    vi.mocked(api.listStartingImageAssets).mockResolvedValue({ items: [startingAsset], total: 1 } as never)
    vi.mocked(api.listArtDirectionReferenceAssets).mockResolvedValue({ items: [], total: 0 } as never)
    render(<ImagesPage />)
    const image = await screen.findByAltText('Starting image for S01A — Assigned')

    fireEvent.error(image)
    expect(screen.getByRole('alert').textContent).toContain(
      'The assigned managed image could not be loaded.',
    )
    fireEvent.change(screen.getByLabelText('Candidate asset'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Clear assignment' }))

    await waitFor(() => expect(saveShot).toHaveBeenCalledTimes(1))
    expect(saveShot.mock.calls[0][1].starting_image_asset_id).toBeNull()
  })
})
