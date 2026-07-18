import type { CharacterReferenceSummary } from '../api/client'

type HeroCandidate = Pick<
  CharacterReferenceSummary,
  'asset_id' | 'approved' | 'order_index' | 'reference_role'
>

export function selectCharacterHeroReference<T extends HeroCandidate>(
  references: readonly T[],
): T | null {
  const ordered = [...references].sort(
    (left, right) => left.order_index - right.order_index,
  )
  const approvedHero = ordered.find(
    (reference) =>
      reference.approved &&
      (reference.reference_role === 'primary' || reference.reference_role === 'hero'),
  )
  if (approvedHero) return approvedHero
  return ordered.find((reference) => !reference.approved) ?? ordered[0] ?? null
}
