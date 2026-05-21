import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { FilePanel } from '../../src/renderer/src/components/FilePanel'

const mockAPI = { listFiles: vi.fn() }

beforeEach(() => {
  vi.clearAllMocks()
  Object.defineProperty(window, 'electronAPI', {
    value: mockAPI,
    writable: true,
    configurable: true,
  })
})

describe('FilePanel', () => {
  it('shows "Loading..." while fetching', () => {
    mockAPI.listFiles.mockReturnValue(new Promise(() => {}))
    render(<FilePanel />)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders file list after load', async () => {
    mockAPI.listFiles.mockResolvedValue([
      { name: 'part.dxf', size: 2048, modified: 1716000000 },
      { name: 'output.nc', size: 512, modified: 1716100000 },
    ])
    render(<FilePanel />)
    await waitFor(() => screen.getByText('part.dxf'))
    expect(screen.getByText('part.dxf')).toBeInTheDocument()
    expect(screen.getByText('output.nc')).toBeInTheDocument()
    expect(screen.getByText('2.0 KB')).toBeInTheDocument()
  })

  it('shows error message on fetch failure', async () => {
    mockAPI.listFiles.mockRejectedValue(new Error('Network error'))
    render(<FilePanel />)
    await waitFor(() => screen.getByText(/Network error/))
  })

  it('shows "No files in workspace" when list is empty', async () => {
    mockAPI.listFiles.mockResolvedValue([])
    render(<FilePanel />)
    await waitFor(() => screen.getByText('No files in workspace'))
  })
})
