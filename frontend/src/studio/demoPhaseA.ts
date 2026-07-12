import {
  normalizePhaseASnapshot,
  type Character,
  type PhaseAShot,
  type PhaseASnapshot,
  type Voice,
} from '../api/client'

const projectId = '11111111-1111-4111-8111-111111111111'
const storyId = '22222222-2222-4222-8222-222222222222'
const alexId = '33333333-3333-4333-8333-333333333333'
const danaId = '44444444-4444-4444-8444-444444444444'
const mayaId = '55555555-5555-4555-8555-555555555555'
const jordanId = '66666666-6666-4666-8666-666666666666'

const characters: Character[] = [
  {
    id: alexId,
    story_id: storyId,
    name: 'Alex Reyes',
    role: 'Lead · New team member',
    approval_state: 'approved',
    physical_description: 'Warm, observant presence; expressive brown eyes; short dark textured hair; grounded posture.',
    age_range: 'Late 20s–mid 30s',
    personality: 'Curious, conscientious, quietly confident',
    speaking_style: 'Thoughtful, direct, receptive',
    wardrobe: 'Soft blue button-up, charcoal trousers, canvas tote',
    consistency_prompt: "Preserve Alex's facial structure, short dark textured hair, warm brown eyes, and understated professional wardrobe.",
    reference_assets: [
      { id: 'ref-alex-hero', asset_id: 'asset-alex-hero', reference_role: 'hero', approved: true, order_index: 0 },
      { id: 'ref-alex-2', asset_id: 'asset-alex-2', reference_role: 'alternate', approved: true, order_index: 1 },
    ],
  },
  {
    id: danaId,
    story_id: storyId,
    name: 'Dana Whitfield',
    role: 'Supervisor',
    approval_state: 'approved',
    physical_description: 'Calm, composed supervisor with silver-streaked dark hair and a reassuring presence.',
    age_range: '40s',
    personality: 'Steady, practical, protective of standards',
    speaking_style: 'Confident, reassuring',
    wardrobe: 'Deep green cardigan, tailored dark trousers',
    reference_assets: [{ id: 'ref-dana-hero', asset_id: 'asset-dana-hero', reference_role: 'hero', approved: true, order_index: 0 }],
  },
  {
    id: mayaId,
    story_id: storyId,
    name: 'Dr. Maya Chen',
    role: 'Clinical mentor',
    approval_state: 'review',
    physical_description: 'Precise, approachable clinician with shoulder-length black hair and attentive posture.',
    age_range: 'Late 30s–40s',
    personality: 'Warm, rigorous, clear',
    speaking_style: 'Precise, approachable',
    wardrobe: 'Clinical navy layers, simple badge lanyard',
    reference_assets: [],
  },
  {
    id: jordanId,
    story_id: storyId,
    name: 'Jordan Blake',
    role: 'Supporting colleague',
    approval_state: 'draft',
    physical_description: 'Friendly colleague with close-cropped hair, relaxed posture, and practical energy.',
    age_range: '30s',
    personality: 'Friendly, observant, pragmatic',
    speaking_style: 'Conversational and field-ready',
    wardrobe: 'Field jacket, neutral shirt, work bag',
    reference_assets: [],
  },
]

const voices: Voice[] = [
  {
    id: '77777777-7777-4777-8777-777777777777',
    story_id: storyId,
    character_id: alexId,
    name: 'Alex · Placeholder 03',
    setup_mode: 'placeholder',
    source_type: 'placeholder_voice',
    consent_confirmed: true,
    consent_required: false,
    approval_state: 'approved',
    provider: 'Local TTS',
    language: 'English',
    accent: 'Neutral US',
    gender_presentation: 'Warm and androgynous',
    tone: 'Curious, grounded',
    speaking_directions: 'Sound thoughtful, never promotional.',
    pacing: '145 wpm',
    energy: 'Calm-medium',
    pronunciation_notes: 'Care Indeed / care in-DEED',
    preview_text: "It’s Alex’s first day—and the beginning of your journey, too.",
  },
  {
    id: '88888888-8888-4888-8888-888888888888',
    story_id: storyId,
    character_id: danaId,
    name: 'Dana · Studio 07',
    setup_mode: 'qwen_voice_design',
    source_type: 'synthetic_voice',
    consent_confirmed: true,
    consent_required: false,
    approval_state: 'approved',
    provider: 'Qwen TTS',
    language: 'English',
    accent: 'West Coast US',
    tone: 'Confident, reassuring',
  },
  {
    id: '99999999-9999-4999-8999-999999999999',
    story_id: storyId,
    character_id: mayaId,
    name: 'Maya · Clinical Clear',
    setup_mode: 'qwen_voice_design',
    source_type: 'synthetic_voice',
    consent_confirmed: true,
    consent_required: false,
    approval_state: 'review',
    provider: 'Qwen TTS',
    language: 'English',
    accent: 'Neutral US',
    tone: 'Precise, approachable',
  },
  {
    id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    story_id: storyId,
    character_id: jordanId,
    name: 'Jordan · Field Note',
    setup_mode: 'user_provided_consented',
    source_type: 'user_provided',
    consent_confirmed: false,
    consent_required: true,
    approval_state: 'blocked',
    provider: 'Local file · mock',
    language: 'English',
    accent: 'Bay Area US',
    tone: 'Conversational',
  },
]

const voiceFor = (characterId: string) =>
  voices.find((voice) => voice.character_id === characterId)?.id ?? null

const shotTitles = [
  ['Morning exterior', 'The welcome email', 'Responsibility', 'The path ahead', 'Step inside'],
  ['Meet Dana', 'A calm welcome', 'The agency promise', 'Your role in the team', 'First-week map'],
  ['The policy guide', 'Why standards matter', 'A home is different', 'Prepare before entry', 'Pause and verify'],
  ['Dr. Chen’s huddle', 'Documentation saves time', 'Escalate early', 'Team backup', 'Respect at the door'],
  ['The first visit brief', 'Read the room', 'Safe handoff', 'Trust is earned'],
  ['Reflection', 'What Alex carries forward', 'Ready to begin'],
]

const durations = [
  [8, 7, 8, 7, 8],
  [7, 8, 7, 7, 8],
  [8, 7, 8, 7, 8],
  [7, 8, 8, 7, 9],
  [8, 10, 10, 10],
  [12, 12, 11],
]

let shotOrder = 0

function makeShot(title: string, duration: number): PhaseAShot {
  const order = shotOrder++
  const approved = order < 10
  const blocked = order === 14
  const review = order >= 10 && order < 17 && !blocked
  const characterId = order < 10 ? alexId : order < 18 ? mayaId : order < 23 ? danaId : jordanId
  const id = `shot-${String(order + 1).padStart(2, '0')}`

  return {
    id,
    order_index: order,
    title,
    duration_sec: duration,
    duration_override_reason: null,
    story_purpose:
      order === 0
        ? "Advance the morning exterior beat while preserving the scene's emotional and instructional continuity."
        : `${title} moves Alex’s first-week learning forward with concrete home-health context.`,
    visual_description:
      order === 0
        ? 'Morning exterior in Care Indeed exterior and reception. Cinematic, grounded performance with restrained production design and clear visual storytelling.'
        : `Cinematic 16:9 planning frame for “${title}” with natural skin detail, restrained healthcare-drama staging, and calm motivated light.`,
    location: order < 10 ? 'Care Indeed exterior and reception' : order < 20 ? 'Care Indeed training room' : 'Home visit preparation space',
    camera_direction: 'Cinematic 16:9 frame, clean eyeline, production-safe composition',
    motion_direction: 'Subtle LTX-ready motion; no identity drift or duplicate people',
    continuity_source_type: order % 5 === 0 ? 'new_generated_image' : 'prior_shot_final_frame',
    continuity_source_shot_id: order > 0 ? `shot-${String(order).padStart(2, '0')}` : null,
    starting_image_required: true,
    starting_image_asset_id: approved || review ? `asset-start-${id}` : null,
    approval_state: blocked ? 'blocked' : approved ? 'approved' : review ? 'review' : 'draft',
    production_status: blocked ? 'blocked' : approved ? 'approved' : review ? 'review' : 'planned',
    blocked_reason: blocked ? 'Reference conflict requires a new approved character image.' : null,
    narration: {
      id: `narration-${id}`,
      voice_profile_id: voiceFor(characterId),
      narration_text:
        order === 0
          ? "It’s Alex’s first day at Care Indeed—and the beginning of your journey, too."
          : `${title} reveals the next practical standard Alex will carry into safe home health care.`,
      start_offset_sec: 0,
      expected_duration_sec: Math.max(3, duration - 2),
      narration_exception_reason: null,
      approval_state: order === 23 || order === 24 ? 'draft' : 'approved',
    },
    prompt_packages: [
      {
        id: `prompt-${id}`,
        version: 1,
        image_prompt: `Cinematic 16:9 frame for “${title}.” Care Indeed grounded healthcare drama, natural skin detail, coherent hands, soft motivated light, production-safe composition.`,
        video_prompt: `Gentle camera drift and restrained performance beat for “${title}”; preserve identity, wardrobe, lighting, eyeline, and screen direction.`,
        negative_prompt: 'identity drift, warped hands, text artifacts, flicker, jitter, duplicate people, oversaturated skin',
        continuity_instructions: 'Preserve identity, wardrobe, lighting, eyeline, and screen direction from the selected continuity source.',
        style_lock_prompt: 'Premium grounded healthcare drama, cinematic realism, restrained teal-and-amber palette, authentic workplace detail.',
        provider_profile_id: order < 10 ? 'flux-dev' : 'sdxl-cineforge',
        provider_model_id: order < 10 ? 'Flux.1 Dev' : 'SDXL CineForge Portrait',
        proposal_id: null,
        approval_state: blocked ? 'blocked' : approved ? 'approved' : review ? 'in_review' : 'draft',
      },
    ],
    characters: [{ character_id: characterId, role_in_shot: 'primary', order_index: 0, continuity_notes: null }],
    recommendations: [],
  }
}

function makeScene(sceneIndex: number) {
  const titles = shotTitles[sceneIndex]
  const sceneShots = titles.map((title, index) => makeShot(title, durations[sceneIndex][index]))
  return {
    id: `scene-${sceneIndex + 1}`,
    order_index: sceneIndex % 2,
    title:
      [
        'Arrival at Care Indeed',
        'The Welcome Conversation',
        'Standards in Action',
        'Mentorship Makes It Practical',
        'Home Readiness',
        'Ready to Begin',
      ][sceneIndex] ?? `Scene ${sceneIndex + 1}`,
    summary:
      sceneIndex === 0
        ? 'Alex enters a new workplace and opens the welcome message.'
        : 'A practical beat connects safe care standards to human decisions.',
    duration_sec: sceneShots.reduce((total, shot) => total + shot.duration_sec, 0),
    shots: sceneShots,
  }
}

const scenes = shotTitles.map((_, index) => makeScene(index))

export const demoPhaseASnapshot: PhaseASnapshot = {
  revision: 'demo-phase-a-v1',
  content_hash: 'demo-a-new-journey',
  planned_duration_sec: 225,
  target_duration_sec: 225,
  discrepancy_sec: 0,
  story: {
    id: storyId,
    project_id: projectId,
    title: 'A New Journey',
    base_story:
      'Alex Reyes joins Care Indeed and meets supervisor Dana Whitfield, clinical mentor Dr. Maya Chen, and colleague Jordan Blake. Across orientation, practical scenarios, and reflection, Alex learns how preparation, documentation, escalation, and teamwork protect patients and earn trust.',
    target_duration_sec: 225,
    logline:
      'On a first day filled with new standards and human stakes, Alex learns that safe care begins long before entering a patient’s home.',
    synopsis:
      'Alex’s first week becomes a guided journey through the responsibilities, relationships, and decisions behind safe home health care.',
    audience: 'New Care Indeed team members',
    tone: 'Warm, confident, human',
    genre: 'Workplace learning drama',
    visual_style: 'Cinematic realism with calm natural light',
    point_of_view: 'Second person alongside Alex',
    production_notes: 'Keep compliance concepts human and visual. Avoid clinical spectacle or generic corporate imagery.',
    approval_state: 'review',
    active_storyboard_version_id: null,
  },
  readiness: {
    ready: false,
    planned_duration_sec: 225,
    target_duration_sec: 225,
    discrepancy_sec: 0,
    reasons: [
      { code: 'target_duration', message: 'Target duration passed.', entity_id: null, blocking: false },
      { code: 'duration_reconciliation', message: 'Duration reconciliation passed.', entity_id: null, blocking: false },
      { code: 'character_approval', message: 'Dr. Maya Chen and Jordan Blake must have approved references.', entity_id: mayaId, blocking: true },
      { code: 'voice_coverage', message: 'Assign voices or narration exceptions to 2 shots.', entity_id: null, blocking: true },
      { code: 'starting_images', message: '17 shots require image approval.', entity_id: null, blocking: true },
      { code: 'continuity', message: 'Repair 1 invalid continuity link.', entity_id: 'shot-15', blocking: true },
      { code: 'model_gap', message: 'Acknowledge or replace the missing CogVideoX checkpoint.', entity_id: null, blocking: true },
      { code: 'blocked_shot', message: 'Resolve the blocked reference conflict.', entity_id: 'shot-15', blocking: true },
    ],
  },
  chapters: [
    {
      id: 'chapter-1',
      order_index: 0,
      title: 'The First Door',
      summary: 'Alex arrives, meets Dana, and learns what the first week will ask.',
      duration_sec: 75,
      scenes: [scenes[0], scenes[1]],
    },
    {
      id: 'chapter-2',
      order_index: 1,
      title: 'Standards in Action',
      summary: 'Policies become practical choices through preparation and clinical mentorship.',
      duration_sec: 77,
      scenes: [scenes[2], scenes[3]],
    },
    {
      id: 'chapter-3',
      order_index: 2,
      title: 'Ready to Begin',
      summary: 'A scenario tests the team, then Alex reflects and steps forward.',
      duration_sec: 73,
      scenes: [scenes[4], scenes[5]],
    },
  ],
  characters,
  voices,
  active_storyboard_version_id: null,
}

export const demoAggregate = normalizePhaseASnapshot(demoPhaseASnapshot)
export const demoReadiness = demoPhaseASnapshot.readiness
