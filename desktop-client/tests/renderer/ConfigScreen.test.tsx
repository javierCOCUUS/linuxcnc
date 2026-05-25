import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ConfigScreen } from '../../src/renderer/src/components/ConfigScreen'

const mockAPI = {
  getHost: vi.fn(),
  setHost: vi.fn(),
  getToken: vi.fn(),
  setToken: vi.fn(),
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.defineProperty(window, 'electronAPI', {
    value: mockAPI,
    writable: true,
    configurable: true,
  })
})

describe('ConfigScreen', () => {
  it('loads and displays stored host and token on mount', async () => {
    mockAPI.getHost.mockResolvedValue('http://192.168.1.10:8006')
    mockAPI.getToken.mockResolvedValue('my-secret-token')

    render(<ConfigScreen />)

    await waitFor(() => {
      expect(screen.getByDisplayValue('http://192.168.1.10:8006')).toBeInTheDocument()
    })
    expect(screen.getByDisplayValue('my-secret-token')).toBeInTheDocument()
  })

  it('calls setHost and setToken with current values on Save click', async () => {
    mockAPI.getHost.mockResolvedValue('http://old:8006')
    mockAPI.getToken.mockResolvedValue('old-token')
    mockAPI.setHost.mockResolvedValue(undefined)
    mockAPI.setToken.mockResolvedValue(undefined)

    render(<ConfigScreen />)
    await waitFor(() => screen.getByDisplayValue('http://old:8006'))

    fireEvent.change(screen.getByPlaceholderText('http://192.168.1.x:8006'), {
      target: { value: 'http://new:8006' }
    })
    fireEvent.click(screen.getByText('Save'))

    await waitFor(() => {
      expect(mockAPI.setHost).toHaveBeenCalledWith('http://new:8006')
      expect(mockAPI.setToken).toHaveBeenCalledWith('old-token')
    })
  })

  it('shows "Saved" confirmation message after save', async () => {
    mockAPI.getHost.mockResolvedValue('http://nas:8006')
    mockAPI.getToken.mockResolvedValue('tok')
    mockAPI.setHost.mockResolvedValue(undefined)
    mockAPI.setToken.mockResolvedValue(undefined)

    render(<ConfigScreen />)
    await waitFor(() => screen.getByDisplayValue('http://nas:8006'))

    fireEvent.click(screen.getByText('Save'))

    await waitFor(() => expect(screen.getByText('Saved')).toBeInTheDocument())
  })
})
