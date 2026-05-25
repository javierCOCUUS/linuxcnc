import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PanelPicker } from '../../src/renderer/src/components/PanelPicker'

describe('PanelPicker', () => {
  it('renders an "Add panel" button', () => {
    render(<PanelPicker onAddPanel={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Add panel' })).toBeInTheDocument()
  })

  it('shows panel type menu on button click', () => {
    render(<PanelPicker onAddPanel={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Add panel' }))
    expect(screen.getByText('Machine Status')).toBeInTheDocument()
    expect(screen.getByText('Position XYZ')).toBeInTheDocument()
    expect(screen.getByText('File Manager')).toBeInTheDocument()
    expect(screen.getByText('Visualizer')).toBeInTheDocument()
    expect(screen.getByText('DXF / CAM')).toBeInTheDocument()
    expect(screen.getByText('G-Code Editor')).toBeInTheDocument()
  })

  it('calls onAddPanel with type and title when an option is clicked', () => {
    const onAddPanel = vi.fn()
    render(<PanelPicker onAddPanel={onAddPanel} />)
    fireEvent.click(screen.getByRole('button', { name: 'Add panel' }))
    fireEvent.click(screen.getByText('Machine Status'))
    expect(onAddPanel).toHaveBeenCalledWith({ type: 'machine-status', title: 'Machine Status' })
  })

  it('closes the menu after selecting a panel type', () => {
    render(<PanelPicker onAddPanel={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Add panel' }))
    fireEvent.click(screen.getByText('Visualizer'))
    expect(screen.queryByText('Machine Status')).not.toBeInTheDocument()
  })
})
