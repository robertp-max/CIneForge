import { describe, expect, it } from 'vitest'

import { selectCharacterHeroReference } from './characterReferences'

const reference = (
  assetId: string,
  role: string,
  approved: boolean,
  orderIndex: number,
) => ({
  id: `link-${assetId}`,
  asset_id: assetId,
  reference_role: role,
  approved,
  order_index: orderIndex,
})

describe('selectCharacterHeroReference', () => {
  it('prefers an approved primary or hero over earlier draft links', () => {
    const selected = selectCharacterHeroReference([
      reference('draft-first', 'identity', false, 0),
      reference('approved-hero', 'hero', true, 2),
      reference('approved-primary', 'primary', true, 1),
    ])

    expect(selected?.asset_id).toBe('approved-primary')
  })

  it('otherwise selects the first linked draft reference by order', () => {
    const selected = selectCharacterHeroReference([
      reference('draft-later', 'alternate', false, 4),
      reference('draft-first', 'identity', false, 1),
    ])

    expect(selected?.asset_id).toBe('draft-first')
  })

  it('returns null only when no reference is linked', () => {
    expect(selectCharacterHeroReference([])).toBeNull()
  })
})
