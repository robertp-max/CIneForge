import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, type Project } from '../api/client'
import { DebugPanel, EmptyState, ErrorNotice, SuccessNotice } from '../components/Cards'
import { PageHeader } from '../components/Page'
import { formatDate } from '../components/formatDate'

type ProjectsProps = {
  mode?: 'list' | 'create'
  onCreateNew?: () => void
  onBackToProjects?: () => void
  onOpenProject?: (projectId: string, projectName?: string) => void
}

export function Projects({
  mode = 'list',
  onCreateNew,
  onBackToProjects,
  onOpenProject,
}: ProjectsProps) {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [lookupId, setLookupId] = useState('')
  const [loading, setLoading] = useState(mode === 'list')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function loadProjects() {
    setLoading(true)
    setError(null)
    try {
      setProjects(await api.listProjects())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load projects.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (mode !== 'list') {
      return
    }
    const timer = window.setTimeout(() => void loadProjects(), 0)
    return () => window.clearTimeout(timer)
  }, [mode])

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const created = await api.createProject({
        name,
        description: description.trim() ? description : null,
      })
      setProjects((current) => [created, ...current.filter((project) => project.id !== created.id)])
      setSelectedProject(created)
      setLookupId(created.id)
      setName('')
      setDescription('')
      setMessage(`Created project "${created.name}".`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create project.')
    } finally {
      setSaving(false)
    }
  }

  async function readProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setMessage(null)
    try {
      const project = await api.getProject(lookupId.trim())
      setSelectedProject(project)
      setMessage(`Loaded project "${project.name}".`)
    } catch (err) {
      setSelectedProject(null)
      setError(err instanceof Error ? err.message : 'Unable to read project.')
    }
  }

  return (
    <div className="page">
      <div className="page-heading-row">
        <PageHeader
          eyebrow="Projects"
          title={mode === 'create' ? 'Create New Project' : 'Project workspace'}
          description={
            mode === 'create'
              ? 'Create a DB-backed CineForge project, then open its planning workspace in Storyboard Studio.'
              : 'Inspect DB-backed CineForge projects and open their planning workspaces in Storyboard Studio.'
          }
        />
        <div className="page-actions">
          {mode === 'list' && onCreateNew ? (
            <button type="button" className="primary-button" onClick={onCreateNew}>
              Create New Project
            </button>
          ) : null}
          {mode === 'create' && onBackToProjects ? (
            <button type="button" className="secondary-button" onClick={onBackToProjects}>
              Back to projects
            </button>
          ) : null}
        </div>
      </div>

      {error ? <ErrorNotice message={error} /> : null}
      {message ? <SuccessNotice message={message} /> : null}

      {mode === 'create' ? (
        <form className="panel form-panel" onSubmit={createProject}>
          <h2>Create Project</h2>
          <label>
            Project name
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Launch Film" />
          </label>
          <label>
            Description
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Hero campaign, cinematic product short, or internal test reel."
            />
          </label>
          <button className="primary-button" disabled={saving} type="submit">
            {saving ? 'Creating...' : 'Create project'}
          </button>
          {selectedProject && onOpenProject ? (
            <button
              className="secondary-button"
              type="button"
              onClick={() => onOpenProject(selectedProject.id, selectedProject.name)}
            >
              Open in Storyboard Studio
            </button>
          ) : null}
        </form>
      ) : null}

      {mode === 'list' ? (
        <section className="form-grid project-lookup-grid">
        <form className="panel form-panel" onSubmit={readProject}>
          <h2>Read Project By ID</h2>
          <label>
            Project ID
            <input value={lookupId} onChange={(event) => setLookupId(event.target.value)} placeholder="UUID" />
          </label>
          <button className="secondary-button" type="submit">
            Load project
          </button>
          {selectedProject ? <DebugPanel title="Selected project response" data={selectedProject} /> : null}
          {selectedProject && onOpenProject ? (
            <button
              className="secondary-button"
              type="button"
              onClick={() => onOpenProject(selectedProject.id, selectedProject.name)}
            >
              Open in Storyboard Studio
            </button>
          ) : null}
        </form>
        </section>
      ) : null}

      {mode === 'list' ? <section className="panel">
        <div className="panel-title">
          <h2>Projects</h2>
          <span>{loading ? 'Loading...' : `${projects.length} total`}</span>
        </div>
        {projects.length === 0 ? (
          <EmptyState
            title="No projects yet."
            detail="Create a project to start organizing campaigns before generation is enabled."
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Description</th>
                  <th>Persistence</th>
                  <th>Created</th>
                  <th>ID</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((project) => (
                  <tr key={project.id}>
                    <td>{project.name}</td>
                    <td>{project.description ?? 'No description'}</td>
                    <td>{project.persistence}</td>
                    <td>{formatDate(project.created_at)}</td>
                    <td className="mono">{project.id}</td>
                    <td>
                      {onOpenProject ? (
                        <button
                          type="button"
                          className="secondary-button project-open-button"
                          onClick={() => onOpenProject(project.id, project.name)}
                        >
                          Open Studio
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section> : null}
    </div>
  )
}
