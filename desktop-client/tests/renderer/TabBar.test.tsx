import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TabBar } from '../../src/renderer/src/components/TabBar'
import type { TabLayout } from '../../src/renderer/src/types/layout'

const tabs: TabLayout[] = [
  { id: 'tab-1', label: 'Workspace 1', dockviewState: null },
  { id: 'tab-2', label: 'Mecanizado', dockviewState: null },
]

describe('TabBar', () => {
  it('renders all tab labels', () => {
    render(<TabBar tabs={tabs} activeTabId="tab-1" onTabClick={vi.fn()} onTabAdd={vi.fn()} onTabRemove={vi.fn()} onTabRename={vi.fn()} />)
    expect(screen.getByText('Workspace 1')).toBeInTheDocument()
    expect(screen.getByText('Mecanizado')).toBeInTheDocument()
  })

  it('marks the active tab with aria-selected="true"', () => {
    render(<TabBar tabs={tabs} activeTabId="tab-1" onTabClick={vi.fn()} onTabAdd={vi.fn()} onTabRemove={vi.fn()} onTabRename={vi.fn()} />)
    const activeTab = screen.getByRole('tab', { name: 'Workspace 1' })
    expect(activeTab).toHaveAttribute('aria-selected', 'true')
    const inactiveTab = screen.getByRole('tab', { name: /Mecanizado/ })
    expect(inactiveTab).toHaveAttribute('aria-selected', 'false')
  })

  it('calls onTabClick with the tab id when a tab is clicked', () => {
    const onTabClick = vi.fn()
    render(<TabBar tabs={tabs} activeTabId="tab-1" onTabClick={onTabClick} onTabAdd={vi.fn()} onTabRemove={vi.fn()} onTabRename={vi.fn()} />)
    fireEvent.click(screen.getByText('Mecanizado'))
    expect(onTabClick).toHaveBeenCalledWith('tab-2')
  })

  it('calls onTabAdd when the + button is clicked', () => {
    const onTabAdd = vi.fn()
    render(<TabBar tabs={tabs} activeTabId="tab-1" onTabClick={vi.fn()} onTabAdd={onTabAdd} onTabRemove={vi.fn()} onTabRename={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'New workspace' }))
    expect(onTabAdd).toHaveBeenCalled()
  })

  it('calls onTabRemove with tab id when the × button inside the tab is clicked', () => {
    const onTabRemove = vi.fn()
    render(<TabBar tabs={tabs} activeTabId="tab-1" onTabClick={vi.fn()} onTabAdd={vi.fn()} onTabRemove={onTabRemove} onTabRename={vi.fn()} />)
    const closeButtons = screen.getAllByRole('button', { name: 'Close tab' })
    fireEvent.click(closeButtons[1])
    expect(onTabRemove).toHaveBeenCalledWith('tab-2')
  })

  it('calls onTabRename with id and new label when tab label is double-clicked and confirmed with Enter', () => {
    const onTabRename = vi.fn()
    render(<TabBar tabs={tabs} activeTabId="tab-1" onTabClick={vi.fn()} onTabAdd={vi.fn()} onTabRemove={vi.fn()} onTabRename={onTabRename} />)
    fireEvent.dblClick(screen.getByText('Workspace 1'))
    const input = screen.getByDisplayValue('Workspace 1')
    fireEvent.change(input, { target: { value: 'New Name' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(onTabRename).toHaveBeenCalledWith('tab-1', 'New Name')
  })
})
