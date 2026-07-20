import { planningAssetContentUrl } from '../api/client'

/** Shot codes used by the published Gold Sites media pack (S01A.webp, …). */
const SHOT_CODE_RE = /\b(S\d{2}[A-Z])\b/i

export function shotCodeFromLabel(value: string | null | undefined): string | null {
  if (!value) return null
  const match = value.match(SHOT_CODE_RE)
  return match ? match[1].toUpperCase() : null
}

/** Published Sites path: /transfiguration/starting-images/S04B.webp */
export function staticStartingImageUrl(code: string): string {
  return `/transfiguration/starting-images/${code.toUpperCase()}.webp`
}

export function staticCharacterImageUrl(slug: string): string {
  return `/transfiguration/characters/${slug.toLowerCase()}.webp`
}

export function staticStoryboardUrl(sceneNumber: number): string {
  return `/transfiguration/storyboards/scene-${String(sceneNumber).padStart(2, '0')}.webp`
}

/**
 * Prefer the published static webp pack (pixel-identical to Sites).
 * Fall back to the managed asset content API when no static code exists.
 */
export function startingFrameUrl(input: {
  title?: string | null
  code?: string | null
  filename?: string | null
  assetId?: string | null
}): string | null {
  const code =
    shotCodeFromLabel(input.code) ||
    shotCodeFromLabel(input.title) ||
    shotCodeFromLabel(input.filename)
  if (code) return staticStartingImageUrl(code)
  if (input.assetId) return planningAssetContentUrl(input.assetId)
  return null
}

export function projectCoverUrl(input: {
  projectName?: string | null
  shotTitles?: Array<string | null | undefined>
  firstAssetId?: string | null
}): string | null {
  for (const title of input.shotTitles ?? []) {
    const url = startingFrameUrl({ title })
    if (url?.startsWith('/transfiguration/')) return url
  }
  // Published Transfiguration cover is exactly S04B.webp
  if ((input.projectName ?? '').toLowerCase().includes('transfiguration')) {
    return staticStartingImageUrl('S04B')
  }
  if (input.firstAssetId) return planningAssetContentUrl(input.firstAssetId)
  return null
}

const CHARACTER_SLUGS: Record<string, string> = {
  jesus: 'jesus',
  peter: 'peter',
  james: 'james',
  john: 'john',
  moses: 'moses',
  elijah: 'elijah',
}

export function characterPortraitUrl(input: {
  name?: string | null
  assetId?: string | null
}): string | null {
  const name = (input.name ?? '').toLowerCase()
  for (const [key, slug] of Object.entries(CHARACTER_SLUGS)) {
    if (name.includes(key)) return staticCharacterImageUrl(slug)
  }
  if (input.assetId) return planningAssetContentUrl(input.assetId)
  return null
}
