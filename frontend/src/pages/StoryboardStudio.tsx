import type { PageId } from '../components/AppShell'
import { StudioProvider } from '../studio/StudioContext'
import { StudioRouter } from '../studio/StudioRouter'

export type StudioPage = PageId

type StoryboardStudioProps = {
  page: StudioPage
  backendStatus: string
  onNavigate: (page: PageId) => void
}

export function StoryboardStudio({ page, backendStatus, onNavigate }: StoryboardStudioProps) {
  return (
    <StudioProvider backendStatus={backendStatus} onNavigate={onNavigate}>
      <StudioRouter page={page} />
    </StudioProvider>
  )
}
