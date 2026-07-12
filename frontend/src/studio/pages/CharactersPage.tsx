import { useState, type FormEvent } from 'react'
import { useStudio } from '../StudioContext'
import { initials } from '../utils'
import { EmptyState } from '../components/StateBlocks'

export function CharactersPage() {
  const { data, addCharacter, busy } = useStudio()
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [description, setDescription] = useState('')

  if (!data) return null

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!name.trim()) return
    await addCharacter({
      name: name.trim(),
      role: role.trim() || undefined,
      description: description.trim() || undefined,
    })
    setName('')
    setRole('')
    setDescription('')
  }

  return (
    <div className="split-2">
      <div className="panel">
        <div className="panel-title">
          <div>
            <h2>Characters</h2>
            <p>
              Identity references and character bibles are planning records. Image generation is
              unavailable in Phase 1 planning.
            </p>
          </div>
        </div>

        {!data.characters.length ? (
          <EmptyState
            title="No characters yet"
            detail="Add cast members as planning records. No assets are generated automatically."
          />
        ) : (
          <div className="people-grid">
            {data.characters.map((item) => (
              <article key={item.id}>
                <span className="avatar" aria-hidden="true">
                  {initials(item.name)}
                </span>
                <b>{item.name}</b>
                <small>
                  {item.role ?? 'Role not specified'} · {item.approval_state}
                </small>
                <p>
                  {item.description?.trim() ||
                    'Reference assets are planned and reviewed here; nothing is generated automatically.'}
                </p>
              </article>
            ))}
          </div>
        )}
      </div>

      <form className="panel stack-form" onSubmit={(event) => void onSubmit(event)}>
        <div className="panel-title">
          <div>
            <h2>Add character</h2>
            <p>Creates a server-side planning record only.</p>
          </div>
        </div>
        <label>
          Name
          <input
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={busy}
            autoComplete="off"
          />
        </label>
        <label>
          Role
          <input value={role} onChange={(event) => setRole(event.target.value)} disabled={busy} />
        </label>
        <label>
          Description / bible notes
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            disabled={busy}
          />
        </label>
        <button type="submit" className="primary-button touch-target" disabled={busy || !name.trim()}>
          Add character
        </button>
        <button type="button" className="secondary-button touch-target" disabled title="Image generation is disabled in planning">
          Generate reference image — disabled
        </button>
        <p className="form-hint">Generate remains disabled: planning never submits ComfyUI work.</p>
      </form>
    </div>
  )
}
