import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, type Project } from '../api/client'
import { DebugPanel, EmptyState, ErrorNotice, SuccessNotice } from '../components/Cards'
import { PageHeader, formatDate } from '../components/Page'

export function Projects() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [lookupId, setLookupId] = useState('')
  const [loading, setLoading] = useState(true)
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
    void loadProjects()
  }, [])

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
      <PageHeader
        eyebrow="Projects"
        title="Project workspace"
        description="Create and inspect DB-backed CineForge projects through the FastAPI backend."
      />

      {error ? <ErrorNotice message={error} /> : null}
      {message ? <SuccessNotice message={message} /> : null}

      <section className="form-grid">
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
        </form>

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
        </form>
      </section>

      <section className="panel">
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
