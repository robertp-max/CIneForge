import { API_BASE_URL } from '../api/client'
import { StatusBadge } from './StatusBadge'
import type { ReactNode } from 'react'

export type PageId =
  | 'dashboard'
  | 'projects'
  | 'campaigns'
  | 'jobs'
  | 'queue'
  | 'runtime'
  | 'health'
  | 'roadmap'

const navItems: { id: PageId; label: string }[] = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'projects', label: 'Projects' },
  { id: 'campaigns', label: 'Campaigns' },
  { id: 'jobs', label: 'Jobs' },
  { id: 'queue', label: 'Queue' },
  { id: 'runtime', label: 'Runtime' },
  { id: 'health', label: 'System Health' },
  { id: 'roadmap', label: 'Roadmap / Disabled Features' },
]

type AppShellProps = {
  activePage: PageId
  backendStatus: string
  onNavigate: (page: PageId) => void
  children: ReactNode
}

export function AppShell({ activePage, backendStatus, onNavigate, children }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">CF</div>
          <div>
            <strong>CineForge</strong>
            <span>Local Control</span>
          </div>
        </div>

        <nav aria-label="Primary navigation">
          {navItems.map((item) => (
            <button
              type="button"
              key={item.id}
              className={item.id === activePage ? 'active' : ''}
              onClick={() => onNavigate(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <StatusBadge status="disabled" label="Generation disabled" />
          <span>Phase 1 readiness boundary is enforced.</span>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">Environment</span>
            <strong>Local MVP</strong>
          </div>
          <div className="topbar-status">
            <span>{API_BASE_URL}</span>
            <StatusBadge status={backendStatus} label={`Backend ${backendStatus}`} />
          </div>
        </header>
        <main>{children}</main>
      </div>
    </div>
  )
}
