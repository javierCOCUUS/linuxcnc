import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import { RoleProvider, useRole } from '../../src/renderer/src/context/RoleContext'

function Show(): JSX.Element {
  return <span data-testid="role">{useRole()}</span>
}

const getRole = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  window.electronAPI = { getRole } as unknown as typeof window.electronAPI
})

describe('RoleContext', () => {
  it('is "machine" without a provider, so isolated panels are not disabled', () => {
    render(<Show />)
    expect(screen.getByTestId('role').textContent).toBe('machine')
  })

  it('starts as "operator" until the backend answers', async () => {
    getRole.mockReturnValue(new Promise(() => {}))
    render(<RoleProvider><Show /></RoleProvider>)
    expect(screen.getByTestId('role').textContent).toBe('operator')
  })

  it('becomes "machine" when the backend says so', async () => {
    getRole.mockResolvedValue({ role: 'machine', operatorEnabled: true })
    render(<RoleProvider><Show /></RoleProvider>)
    await waitFor(() => expect(screen.getByTestId('role').textContent).toBe('machine'))
  })

  it('stays "operator" when the backend says operator', async () => {
    getRole.mockResolvedValue({ role: 'operator', operatorEnabled: true })
    render(<RoleProvider><Show /></RoleProvider>)
    await act(async () => { await Promise.resolve() })
    expect(screen.getByTestId('role').textContent).toBe('operator')
  })

  it('stays "operator" when the backend cannot be reached', async () => {
    getRole.mockRejectedValue(new Error('network down'))
    render(<RoleProvider><Show /></RoleProvider>)
    await act(async () => { await Promise.resolve() })
    expect(screen.getByTestId('role').textContent).toBe('operator')
  })
})
