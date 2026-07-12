import { useMemo, useState, type FormEvent } from 'react'
import {
  api,
  VOICE_SOURCE_MODE_LABELS,
  VOICE_SOURCE_MODES,
  type VoiceSourceMode,
} from '../../api/client'
import { useStudio } from '../StudioContext'
import { EmptyState, ErrorState } from '../components/StateBlocks'

function modeRequiresConsent(mode: VoiceSourceMode): boolean {
  return mode === 'user_provided'
}

export function VoicesPage() {
  const { data, addVoice, busy, setMessage } = useStudio()
  const [name, setName] = useState('')
  const [mode, setMode] = useState<VoiceSourceMode>('placeholder')
  const [language, setLanguage] = useState('en')
  const [notes, setNotes] = useState('')
  const [consentConfirmed, setConsentConfirmed] = useState(false)
  const [previewBusyId, setPreviewBusyId] = useState<string | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [previewNote, setPreviewNote] = useState<string | null>(null)

  const consentRequired = modeRequiresConsent(mode)

  const modeHelp = useMemo(() => {
    switch (mode) {
      case 'placeholder':
        return 'Planning stand-in. No provider call and no audio generation.'
      case 'stock_library':
        return 'Reference a licensed stock voice catalog entry. Preview is provider-safe only.'
      case 'user_provided':
        return 'User-supplied sample. Consent must be confirmed. Cloning is never performed automatically.'
      case 'narration':
        return 'Narration planning profile for story-level VO.'
      case 'dialogue':
        return 'Character dialogue planning profile.'
      case 'voiceover':
        return 'Commercial / instructional voiceover planning profile.'
      case 'ambient':
        return 'Ambient or background voice bed planning only.'
      case 'tts_synthetic':
        return 'Synthetic TTS is planning metadata only — no batch synthesis on save.'
      default:
        return ''
    }
  }, [mode])

  if (!data) return null

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!name.trim()) return
    if (consentRequired && !consentConfirmed) {
      setMessage('Confirm consent before saving a user-provided voice source.')
      return
    }
    await addVoice({
      name: name.trim(),
      source_type: mode,
      consent_required: consentRequired,
      consent_confirmed: consentRequired ? consentConfirmed : false,
      language: language.trim() || undefined,
      notes: notes.trim() || undefined,
    })
    setName('')
    setNotes('')
    setConsentConfirmed(false)
    setMode('placeholder')
  }

  const onPreview = async (voiceId: string) => {
    setPreviewBusyId(voiceId)
    setPreviewError(null)
    setPreviewNote(null)
    try {
      const result = await api.previewVoice(voiceId, {
        text: 'CineForge provider-safe voice preview. Planning only.',
      })
      if (!result) {
        setPreviewError(
          'Voice preview API is unavailable on this backend. No audio was generated locally.',
        )
        setMessage('Preview unavailable: backend did not expose a provider-safe preview endpoint.')
        return
      }
      if (result.generation_performed) {
        setPreviewNote(
          `${result.message} Provider reported a preview artifact; cloning/final mix was not requested by this UI.`,
        )
      } else {
        setPreviewNote(result.message || 'Preview acknowledged without generation.')
      }
      if (result.preview_url) {
        // Open only server-provided URL; never invent one.
        window.open(result.preview_url, '_blank', 'noopener,noreferrer')
      }
      setMessage(`Preview action completed for voice ${voiceId}.`)
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Preview failed.'
      setPreviewError(text)
      setMessage(text)
    } finally {
      setPreviewBusyId(null)
    }
  }

  return (
    <div className="split-2">
      <div className="panel">
        <div className="panel-title">
          <div>
            <h2>Voice profiles</h2>
            <p>
              Exact eight source modes. User-provided sources require confirmed consent. Voice cloning
              is not available as an automatic action.
            </p>
          </div>
        </div>

        {!data.voices.length ? (
          <EmptyState
            title="No voice profiles"
            detail="Add a planning voice using one of the eight source modes."
          />
        ) : (
          <div className="people-grid">
            {data.voices.map((voice) => {
              const label =
                VOICE_SOURCE_MODE_LABELS[voice.source_type as VoiceSourceMode] ?? voice.source_type
              const previewDisabled =
                busy || previewBusyId === voice.id || voice.preview_available === false
              return (
                <article key={voice.id}>
                  <b>{voice.name}</b>
                  <small>
                    {label} · {voice.approval_state}
                  </small>
                  <p>
                    {voice.consent_confirmed
                      ? 'Consent confirmed'
                      : voice.consent_required
                        ? 'Consent required — not confirmed'
                        : 'No consent required for this mode'}
                  </p>
                  {voice.language ? <small>Language: {voice.language}</small> : null}
                  {voice.notes ? <p>{voice.notes}</p> : null}
                  <div className="inline-actions">
                    <button
                      type="button"
                      className="secondary-button touch-target"
                      disabled={previewDisabled}
                      title={
                        voice.preview_available === false
                          ? 'Server reports preview unavailable for this profile'
                          : 'Provider-safe preview only — does not clone or mix final audio'
                      }
                      onClick={() => void onPreview(voice.id)}
                    >
                      {previewBusyId === voice.id ? 'Previewing…' : 'Provider-safe preview'}
                    </button>
                    <button
                      type="button"
                      className="ghost-button touch-target"
                      disabled
                      title="Voice cloning is not available"
                    >
                      Clone voice — disabled
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
        )}

        {previewError ? <ErrorState title="Preview error" detail={previewError} /> : null}
        {previewNote ? (
          <p className="notice info" role="status">
            {previewNote}
          </p>
        ) : null}
      </div>

      <form className="panel stack-form" onSubmit={(event) => void onSubmit(event)}>
        <div className="panel-title">
          <div>
            <h2>Add voice profile</h2>
            <p>Select one of the eight modes. Save writes planning data only.</p>
          </div>
        </div>

        <fieldset style={{ border: 0, margin: 0, padding: 0 }}>
          <legend className="eyebrow">Source mode (8)</legend>
          <div className="mode-grid" role="group" aria-label="Voice source modes">
            {VOICE_SOURCE_MODES.map((item) => (
              <button
                key={item}
                type="button"
                className={`mode-option ${mode === item ? 'selected' : ''}`}
                aria-pressed={mode === item}
                onClick={() => {
                  setMode(item)
                  if (!modeRequiresConsent(item)) setConsentConfirmed(false)
                }}
                disabled={busy}
              >
                {VOICE_SOURCE_MODE_LABELS[item]}
                <small>{item}</small>
              </button>
            ))}
          </div>
          <p className="form-hint">{modeHelp}</p>
        </fieldset>

        <label>
          Profile name
          <input
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={busy}
            autoComplete="off"
          />
        </label>

        <label>
          Language
          <input value={language} onChange={(event) => setLanguage(event.target.value)} disabled={busy} />
        </label>

        <label>
          Notes
          <textarea value={notes} onChange={(event) => setNotes(event.target.value)} disabled={busy} />
        </label>

        {consentRequired ? (
          <label style={{ gridTemplateColumns: 'auto 1fr', alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={consentConfirmed}
              onChange={(event) => setConsentConfirmed(event.target.checked)}
              disabled={busy}
              style={{ width: 20, height: 20, minHeight: 20 }}
            />
            <span>I confirm rights/consent for this user-provided voice sample.</span>
          </label>
        ) : (
          <p className="form-hint">Consent checkbox is only required for user-provided samples.</p>
        )}

        <button
          type="submit"
          className="primary-button touch-target"
          disabled={busy || !name.trim() || (consentRequired && !consentConfirmed)}
        >
          Save voice profile
        </button>
        <button
          type="button"
          className="secondary-button touch-target"
          disabled
          title="Automatic cloning and batch TTS are disabled in planning"
        >
          Generate / clone audio — disabled
        </button>
      </form>
    </div>
  )
}
