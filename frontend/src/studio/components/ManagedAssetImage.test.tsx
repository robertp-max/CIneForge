import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { ManagedAssetImage } from './ManagedAssetImage'

afterEach(cleanup)

describe('ManagedAssetImage', () => {
  it('shows the intentional fallback when no asset is assigned', () => {
    render(
      <ManagedAssetImage
        assetId={null}
        alt="Character reference"
        errorLabel="Reference bytes unavailable"
        fallback={<span>CF</span>}
      />,
    )

    expect(screen.getByText('CF')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('replaces a failed image with an explicit unavailable alert, not initials', () => {
    render(
      <ManagedAssetImage
        assetId="asset-broken"
        alt="Character reference"
        errorLabel="Reference bytes unavailable"
        fallback={<span>CF</span>}
      />,
    )

    fireEvent.error(screen.getByAltText('Character reference'))

    const alert = screen.getByRole('alert')
    expect(alert.textContent).toContain('Reference bytes unavailable')
    expect(alert.textContent).toContain('asset-broken')
    expect(screen.queryByText('CF')).toBeNull()
    expect(screen.queryByAltText('Character reference')).toBeNull()
  })
})
