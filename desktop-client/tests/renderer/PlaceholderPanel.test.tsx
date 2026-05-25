import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PlaceholderPanel } from '../../src/renderer/src/components/panels/PlaceholderPanel'

describe('PlaceholderPanel', () => {
  it('renders the panel type label for known types', () => {
    render(<PlaceholderPanel type="machine-status" />)
    expect(screen.getByText('Machine Status')).toBeInTheDocument()
  })

  it('renders placeholder hint text', () => {
    render(<PlaceholderPanel type="visualizer" />)
    expect(screen.getByText('— available in a future phase —')).toBeInTheDocument()
  })

  it('handles unknown type by showing the raw type string', () => {
    render(<PlaceholderPanel type="custom-unknown" />)
    expect(screen.getByText('custom-unknown')).toBeInTheDocument()
  })
})
