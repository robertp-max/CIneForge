/**
 * Maps production storyboard aggregate / readiness into the prototype page
 * view-model shape used by ported ZIP components.
 *
 * Production APIs remain authoritative. This is a presentation adapter only.
 */
import type { Readiness, StoryboardAggregate } from '../../api/client'
import { countScenes, countShots, formatDuration } from '../utils'

export type ProtoStatus = 'Draft' | 'Review' | 'Approved' | 'Blocked' | 'Ready'

export type ProtoGate = { label: string; pass: boolean; reason: string }

export type ProtoShot = {
  id: string
  title: string
  duration: number
  status: ProtoStatus
  startingImageStatus: ProtoStatus
  continuityValid: boolean
  voiceId: string | null
  label: string
  chapterId: string
  sceneId: string
  visualDescription: string
  storyPurpose: string
  characterIds: string[]
  imageModel: string
  videoModel: string
  workflow: string
  resolution: string
  fps: number
  seedPolicy: string
  risk: string
  display_label?: string
}

export type ProtoProject = {
  name: string
  synopsis: string
  orchestratorModel: string
  approvedPlan: boolean
  chapters: Array<{ id: string; title: string; duration: number; sceneIds: string[] }>
  scenes: Array<{ id: string; title: string; chapterId: string; shotIds: string[]; summary?: string }>
  shots: ProtoShot[]
  characters: Array<{
    id: string
    name: string
    role: string
    initials: string
    status: ProtoStatus
    heroApproved: boolean
    references: number
    description: string
  }>
  voices: Array<{ id: string; name: string; characterId: string | null; status: ProtoStatus }>
  workflows: Array<{ id: string; name: string; installed: boolean; type: string }>
  routing: Array<{
    task: string
    provider: string
    model: string
    mode: string
    privacy: string
    availability: string
    speed: string
    cost: string
    reason: string
  }>
}

function approvalToStatus(value: string | null | undefined): ProtoStatus {
  const v = (value ?? 'draft').toLowerCase()
  if (v === 'approved') return 'Approved'
  if (v === 'blocked') return 'Blocked'
  if (v === 'in_review' || v === 'review') return 'Review'
  return 'Draft'
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '??'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0] ?? ''}${parts[1][0] ?? ''}`.toUpperCase()
}

export function toProtoProject(
  data: StoryboardAggregate,
  readiness: Readiness | null,
): {
  project: ProtoProject
  plannedRuntime: number
  readinessPct: number
  gates: ProtoGate[]
  targetRuntimeLabel: string
  plannedRuntimeLabel: string
} {
  const chapters = data.chapters.map((chapter) => ({
    id: chapter.id,
    title: chapter.title,
    duration: chapter.duration_sec,
    sceneIds: chapter.scenes.map((s) => s.id),
  }))
  const scenes = data.chapters.flatMap((chapter) =>
    chapter.scenes.map((scene) => ({
      id: scene.id,
      title: scene.title,
      chapterId: chapter.id,
      shotIds: scene.shots.map((s) => s.id),
      summary: scene.summary ?? '',
    })),
  )
  const shots: ProtoShot[] = data.chapters.flatMap((chapter) =>
    chapter.scenes.flatMap((scene) =>
      scene.shots.map((shot) => ({
        id: shot.id,
        title: shot.title,
        duration: shot.duration_sec,
        status: approvalToStatus(shot.approval_state),
        startingImageStatus: shot.starting_image_asset_id
          ? approvalToStatus(shot.approval_state)
          : shot.starting_image_required
            ? 'Blocked'
            : 'Draft',
        continuityValid: Boolean(shot.continuity_source_type && shot.continuity_source_type !== 'none'),
        voiceId: shot.narration_voice_profile_id ?? null,
        label: shot.display_label || 'A',
        chapterId: chapter.id,
        sceneId: scene.id,
        visualDescription: shot.visual_description || '',
        storyPurpose: shot.story_purpose || '',
        characterIds: (shot.characters ?? []).map((c) => c.character_id),
        imageModel:
          shot.recommendations?.find((r) => r.recommendation_type === 'generation')?.rationale ||
          'Unknown',
        videoModel:
          shot.recommendations?.find((r) => r.recommendation_type === 'workflow')?.rationale ||
          'Unknown',
        workflow: 'Planning workflow',
        resolution: '1280×720',
        fps: 24,
        seedPolicy: 'Fixed',
        risk: shot.approval_state === 'blocked' ? 'Blocked' : 'Ready',
        display_label: shot.display_label,
      })),
    ),
  )

  const characters = data.characters.map((c) => ({
    id: c.id,
    name: c.name,
    role: c.role || 'Character',
    initials: initials(c.name),
    status: approvalToStatus(c.approval_state),
    heroApproved:
      c.approval_state === 'approved' ||
      Boolean(c.reference_assets?.some((r) => r.approved && (r.reference_role === 'hero' || r.reference_role === 'primary'))),
    references: c.reference_assets?.length ?? 0,
    description: c.physical_description || '',
  }))

  const voices = data.voices.map((v) => ({
    id: v.id,
    name: v.name,
    characterId: v.character_id ?? null,
    status: approvalToStatus(v.approval_state),
  }))

  const gates: ProtoGate[] =
    readiness?.reasons?.length
      ? readiness.reasons.map((reason) => ({
          label: reason.code,
          pass: !reason.blocking,
          reason: reason.message,
        }))
      : [
          {
            label: readiness?.ready ? 'ready' : 'pending',
            pass: Boolean(readiness?.ready),
            reason: readiness?.ready
              ? 'All current backend readiness checks pass.'
              : 'Readiness reasons have not been returned yet.',
          },
        ]

  const planned = readiness?.planned_duration_sec ?? shots.reduce((n, s) => n + s.duration, 0)
  const target = readiness?.target_duration_sec ?? data.story.target_duration_sec
  const blocking = gates.filter((g) => !g.pass).length
  const readinessPct = readiness?.ready
    ? 100
    : Math.max(8, Math.min(92, 100 - blocking * 12))

  return {
    project: {
      name: data.story.title,
      synopsis: data.story.synopsis || data.story.logline || data.story.base_story || '',
      orchestratorModel: 'Planning orchestrator',
      approvedPlan: data.story.approval_state === 'approved',
      chapters,
      scenes,
      shots,
      characters,
      voices,
      workflows: [],
      routing: [],
    },
    plannedRuntime: planned,
    readinessPct,
    gates,
    targetRuntimeLabel: formatDuration(target),
    plannedRuntimeLabel: formatDuration(planned),
  }
}

export function chapterNote(project: ProtoProject): string {
  if (!project.chapters.length) return 'No chapters'
  return project.chapters.map((c) => `${c.duration}s`).join(' · ')
}

export function coverageNote(have: number, total: number, openLabel: string): string {
  const open = Math.max(0, total - have)
  return open ? `${open} ${openLabel}` : 'Complete'
}

export { countScenes, countShots, formatDuration }
