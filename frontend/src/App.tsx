import { useState } from 'react'
import { AppShell, type PageId } from './components/AppShell'
import { StoryboardStudio } from './pages/StoryboardStudio'

function App() {
  const [activePage, setActivePage] = useState<PageId>('overview')
  const [backendStatus] = useState('checking')

  return (
    <AppShell activePage={activePage} backendStatus={backendStatus} onNavigate={setActivePage}>
      <StoryboardStudio page={activePage} />
    </AppShell>
  )
}

export default App
