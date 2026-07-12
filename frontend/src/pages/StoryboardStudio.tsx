import type { PageId } from '../components/AppShell'
import { StudioRouter } from '../studio/StudioRouter'

export type StudioPage = PageId

type StoryboardStudioProps = {
  page: StudioPage
  /** Kept for call-site compatibility; provider is owned by App. */
  backendStatus?: string
  onNavigate?: (page: PageId) => void
}

export function StoryboardStudio({ page }: StoryboardStudioProps) {
  return <StudioRouter page={page} />
}
