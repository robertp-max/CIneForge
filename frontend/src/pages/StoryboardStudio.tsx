import type { PageId } from '../components/AppShell'
import { StudioProvider } from '../studio/StudioContext'
import { StudioRouter } from '../studio/StudioRouter'

export type StudioPage = PageId

type StoryboardStudioProps = {
  page: StudioPage
  projectId: string
  backendStatus: string
  onNavigate: (page: PageId) => void
}

export function StoryboardStudio({ page, projectId, backendStatus, onNavigate }: StoryboardStudioProps) {
  return (
    <StudioProvider projectId={projectId} backendStatus={backendStatus} onNavigate={onNavigate}>
      <StudioRouter page={page} />
    </StudioProvider>
  )
}
