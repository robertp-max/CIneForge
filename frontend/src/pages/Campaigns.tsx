import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, type Campaign, type Project } from '../api/client'
import { DebugPanel, EmptyState, ErrorNotice, SuccessNotice } from '../components/Cards'
import { PageHeader, formatDate } from '../components/Page'

export function Campaigns() {
  const [projects, setProjects] = useState<Project[]>([])
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null)
  const [projectId, setProjectId] = useState('')
  const [name, setName] = useState('')
  const [targetDuration, setTargetDuration] = useState('')
  const [lookupId, setLookupId] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function loadData() {
    setLoading(true)
    setError(null)
    try {
      const [projectList, campaignList] = await Promise.all([api.listProjects(), api.listCampaigns()])
      setProjects(projectList)
      setCampaigns(campaignList)
      setProjectId((current) => current || projectList[0]?.id || '')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load campaigns.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  async function createCampaign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const duration = targetDuration.trim() ? Number(targetDuration) : null
      const created = await api.createCampaign({
        project_id: projectId,
        name,
        target_duration_sec: duration,
      })
      setCampaigns((current) => [created, ...current.filter((campaign) => campaign.id !== created.id)])
      setSelectedCampaign(created)
      setLookupId(created.id)
      setName('')
      setTargetDuration('')
      setMessage(`Created campaign "${created.name}".`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create campaign.')
    } finally {
      setSaving(false)
    }
  }

  async function readCampaign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setMessage(null)
    try {
      const campaign = await api.getCampaign(lookupId.trim())
      setSelectedCampaign(campaign)
      setMessage(`Loaded campaign "${campaign.name}".`)
    } catch (err) {
      setSelectedCampaign(null)
      setError(err instanceof Error ? err.message : 'Unable to read campaign.')
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Campaigns"
        title="Campaign planning"
        description="Create campaign records under an existing project and keep target duration visible before generation opens."
      />

      {error ? <ErrorNotice message={error} /> : null}
      {message ? <SuccessNotice message={message} /> : null}

      <section className="form-grid">
        <form className="panel form-panel" onSubmit={createCampaign}>
          <h2>Create Campaign</h2>
          <label>
            Project
            <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
              <option value="">Select a project</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Campaign name
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Episode One" />
          </label>
          <label>
            Target duration seconds
            <input
              value={targetDuration}
              onChange={(event) => setTargetDuration(event.target.value)}
              placeholder="30"
              type="number"
              min="0.1"
              step="0.1"
            />
          </label>
          <button className="primary-button" disabled={saving || !projectId} type="submit">
            {saving ? 'Creating...' : 'Create campaign'}
          </button>
          {projects.length === 0 ? (
            <p className="form-hint">Create a project before adding a campaign.</p>
          ) : null}
        </form>

        <form className="panel form-panel" onSubmit={readCampaign}>
          <h2>Read Campaign By ID</h2>
          <label>
            Campaign ID
            <input value={lookupId} onChange={(event) => setLookupId(event.target.value)} placeholder="UUID" />
          </label>
          <button className="secondary-button" type="submit">
            Load campaign
          </button>
          {selectedCampaign ? <DebugPanel title="Selected campaign response" data={selectedCampaign} /> : null}
        </form>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Campaigns</h2>
          <span>{loading ? 'Loading...' : `${campaigns.length} total`}</span>
        </div>
        {campaigns.length === 0 ? (
          <EmptyState
            title="No campaigns yet."
            detail="Campaigns connect a project to duration goals. Generation jobs stay disabled until Phase 2."
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Project</th>
                  <th>Target Duration</th>
                  <th>Persistence</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((campaign) => {
                  const project = projects.find((item) => item.id === campaign.project_id)
                  return (
                    <tr key={campaign.id}>
                      <td>{campaign.name}</td>
                      <td>{project?.name ?? campaign.project_id}</td>
                      <td>{campaign.target_duration_sec ? `${campaign.target_duration_sec}s` : 'Not set'}</td>
                      <td>{campaign.persistence}</td>
                      <td>{formatDate(campaign.created_at)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
