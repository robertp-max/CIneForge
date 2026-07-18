import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import { Projects } from './Projects'

vi.mock('../api/client', () => ({
  api: {
    createProjectWorkspace: vi.fn(),
  },
}))

const workspace = {
  project: {
    id: 'project-1',
    name: 'The Test Film',
    description: 'A test',
    created_at: '2026-07-17T00:00:00Z',
    persistence: 'db',
  },
  story: { id: 'story-1' },
  settings: { id: 'settings-1' },
  idempotent_replay: false,
}

function reachFinalStep() {
  fireEvent.change(screen.getByPlaceholderText('e.g. The Transfiguration'), {
    target: { value: 'The Test Film' },
  })
  fireEvent.change(screen.getByPlaceholderText('What are you creating, and what should the audience experience?'), {
    target: { value: 'A test' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Continue →' }))
  fireEvent.change(screen.getByPlaceholderText('Paste the complete source material here…'), {
    target: { value: 'The complete source.' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Continue →' }))
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('new project workspace', () => {
  it('submits the wizard once and preserves its story and production values', async () => {
    vi.mocked(api.createProjectWorkspace).mockResolvedValue(workspace as never)
    const onOpenProject = vi.fn()
    render(<Projects mode="create" onOpenProject={onOpenProject} />)
    reachFinalStep()

    fireEvent.change(screen.getByLabelText('Audience'), { target: { value: 'Families' } })
    fireEvent.change(screen.getByLabelText('Aspect ratio'), { target: { value: '2.39:1' } })
    fireEvent.change(screen.getByLabelText('Frame rate'), { target: { value: '30' } })
    fireEvent.change(screen.getByLabelText('Privacy preference'), {
      target: { value: 'Hosted providers allowed' },
    })
    fireEvent.click(screen.getByRole('button', { name: '✦ Create project' }))

    await waitFor(() => expect(api.createProjectWorkspace).toHaveBeenCalledTimes(1))
    expect(api.createProjectWorkspace).toHaveBeenCalledWith(expect.objectContaining({
      name: 'The Test Film',
      description: 'A test',
      base_story: 'The complete source.',
      audience: 'Families',
      aspect_ratio: '2.39:1',
      preview_width: 1280,
      preview_height: 536,
      final_width: 1920,
      final_height: 804,
      fps: 30,
      captions_enabled: true,
      audio_enabled: true,
      speaking_rate: 1,
      prefer_hosted_providers: true,
      prefer_local_providers: true,
      allow_model_download: false,
      allow_rendering: false,
      require_production_plan_approval: true,
    }))
    expect(onOpenProject).toHaveBeenCalledWith('project-1', 'The Test Film')
  })

  it('shows a useful failure and reuses the idempotency key on retry', async () => {
    vi.mocked(api.createProjectWorkspace)
      .mockRejectedValueOnce(new Error('Workspace creation failed safely; no partial project was kept.'))
      .mockResolvedValueOnce(workspace as never)
    render(<Projects mode="create" />)
    reachFinalStep()

    fireEvent.click(screen.getByRole('button', { name: '✦ Create project' }))
    expect((await screen.findByRole('alert')).textContent).toContain(
      'Workspace creation failed safely; no partial project was kept.',
    )
    fireEvent.click(screen.getByRole('button', { name: '✦ Create project' }))

    await waitFor(() => expect(api.createProjectWorkspace).toHaveBeenCalledTimes(2))
    const firstKey = vi.mocked(api.createProjectWorkspace).mock.calls[0][0].idempotency_key
    const secondKey = vi.mocked(api.createProjectWorkspace).mock.calls[1][0].idempotency_key
    expect(secondKey).toBe(firstKey)
  })
})
