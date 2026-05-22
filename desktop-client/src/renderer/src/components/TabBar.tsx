import { useState } from 'react'
import type { TabLayout } from '../types/layout'

interface TabBarProps {
  tabs: TabLayout[]
  activeTabId: string
  onTabClick: (id: string) => void
  onTabAdd: () => void
  onTabRemove: (id: string) => void
  onTabRename: (id: string, label: string) => void
}

export function TabBar({ tabs, activeTabId, onTabClick, onTabAdd, onTabRemove, onTabRename }: TabBarProps): JSX.Element {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  function startRename(tab: TabLayout): void {
    setEditingId(tab.id)
    setEditValue(tab.label)
  }

  function commitRename(id: string): void {
    if (editValue.trim()) onTabRename(id, editValue.trim())
    setEditingId(null)
  }

  return (
    <div className="tab-bar" role="tablist">
      {tabs.map(tab => (
        <div
          key={tab.id}
          role="tab"
          aria-label={tab.label}
          aria-selected={tab.id === activeTabId}
          className={`tab-item ${tab.id === activeTabId ? 'tab-active' : ''}`}
          onClick={() => onTabClick(tab.id)}
        >
          {editingId === tab.id ? (
            <input
              className="tab-rename-input"
              value={editValue}
              autoFocus
              onChange={e => setEditValue(e.target.value)}
              onBlur={() => commitRename(tab.id)}
              onKeyDown={e => {
                if (e.key === 'Enter') commitRename(tab.id)
                if (e.key === 'Escape') setEditingId(null)
              }}
              onClick={e => e.stopPropagation()}
            />
          ) : (
            <span
              className="tab-label"
              onDoubleClick={e => { e.stopPropagation(); startRename(tab) }}
            >
              {tab.label}
            </span>
          )}
          <button
            className="tab-close"
            aria-label="Close tab"
            onClick={e => { e.stopPropagation(); onTabRemove(tab.id) }}
          >
            ×
          </button>
        </div>
      ))}
      <button
        className="tab-add"
        aria-label="New workspace"
        onClick={onTabAdd}
      >
        +
      </button>
    </div>
  )
}
