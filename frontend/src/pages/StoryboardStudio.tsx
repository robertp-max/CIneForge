import type { PageId } from '../components/AppShell'
import { StudioProvider } from '../studio/StudioContext'
import { StudioRouter } from '../studio/StudioRouter'

export type StudioPage = PageId

type StoryboardStudioProps = {
  page: StudioPage
  backendStatus: string
}

export function StoryboardStudio({ page, backendStatus }: StoryboardStudioProps) {
  return (
    <StudioProvider backendStatus={backendStatus}>
      <StudioRouter page={page} />
    </StudioProvider>
  )
}
