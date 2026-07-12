import type { PageId } from '../components/AppShell'
import { useStudio } from './StudioContext'
import { StudioChrome } from './components/StudioChrome'
import { StoryBootstrap } from './components/StoryBootstrap'
import { OverviewPage } from './pages/OverviewPage'
import { StoryboardPage } from './pages/StoryboardPage'
import { StoryPage } from './pages/StoryPage'
import { CharactersPage } from './pages/CharactersPage'
import { VoicesPage } from './pages/VoicesPage'
import { ImagesPage } from './pages/ImagesPage'
import { RoutingPage } from './pages/RoutingPage'
import { WorkflowsPage } from './pages/WorkflowsPage'
import { ExportsPage } from './pages/ExportsPage'
import { SettingsPage } from './pages/SettingsPage'

const PAGE_META: Record<PageId, { title: string; description: string }> = {
  overview: {
    title: 'Overview',
    description: 'Production readiness, hierarchy counts, and approval gates from the backend.',
  },
  storyboard: {
    title: 'Storyboard',
    description: 'Ordered Chapter → Scene → Shot hierarchy with shot inspector.',
  },
  story: {
    title: 'Story & Chapters',
    description: 'Story intake, synopsis, and ordered chapter structure.',
  },
  characters: {
    title: 'Characters',
    description: 'Identity references and character bibles as planning records only.',
  },
  voices: {
    title: 'Voices',
    description: 'Eight voice source modes, consent gates, and provider-safe previews.',
  },
  images: {
    title: 'Starting Images',
    description: 'Plan approved reference assets. Image generation remains disabled in planning.',
  },
  routing: {
    title: 'Model Routing',
    description: 'Provider and model proposals only — Unknown until registry evidence exists.',
  },
  workflows: {
    title: 'Workflows',
    description: 'Workflow readiness from the backend registry; no install or queue actions.',
  },
  exports: {
    title: 'Exports',
    description: 'Planning exports for stored hierarchy. Render packages remain unavailable.',
  },
  settings: {
    title: 'Project Settings',
    description: 'Duration, approval, continuity, consent, and aspect policies from the server.',
  },
}

export function StudioRouter({ page }: { page: PageId }) {
  const { data, loadState } = useStudio()

  if (!data || loadState === 'empty') {
    return <StoryBootstrap />
  }

  const meta = PAGE_META[page]
  const content = {
    overview: <OverviewPage />,
    storyboard: <StoryboardPage />,
    story: <StoryPage />,
    characters: <CharactersPage />,
    voices: <VoicesPage />,
    images: <ImagesPage />,
    routing: <RoutingPage />,
    workflows: <WorkflowsPage />,
    exports: <ExportsPage />,
    settings: <SettingsPage />,
  }[page]

  return (
    <StudioChrome title={meta.title} description={meta.description}>
      {content}
    </StudioChrome>
  )
}
