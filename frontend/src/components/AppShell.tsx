import { API_BASE_URL } from '../api/client'
import { StatusBadge } from './StatusBadge'
import type { ReactNode } from 'react'

export type PageId =
  | 'overview'
  | 'storyboard'
  | 'story'
  | 'characters'
  | 'voices'
  | 'images'
  | 'routing'
  | 'workflows'
  | 'exports'
  | 'settings'

const navItems: { id: PageId; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'storyboard', label: 'Storyboard' },
  { id: 'story', label: 'Story & Chapters' },
  { id: 'characters', label: 'Characters' },
  { id: 'voices', label: 'Voices' },
  { id: 'images', label: 'Starting Images' },
  { id: 'routing', label: 'Model Routing' },
  { id: 'workflows', label: 'Workflows' },
  { id: 'exports', label: 'Exports' },
  { id: 'settings', label: 'Project Settings' },
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
            <span>Storyboard Studio · Phase A</span>
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
          <StatusBadge status="disabled" label="Rendering disabled" />
          <span>Planning ends with an approved editable production plan.</span>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">Environment</span>
            <strong>Production planning</strong>
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
