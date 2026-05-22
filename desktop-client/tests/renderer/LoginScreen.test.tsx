import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const mockElectronAPI = {
  odooLogin: vi.fn(),
}
Object.defineProperty(window, 'electronAPI', { value: mockElectronAPI, writable: true })

import { LoginScreen } from '../../src/renderer/src/components/LoginScreen'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('LoginScreen', () => {
  it('renders Odoo URL, Username, Password fields and Login button', () => {
    render(<LoginScreen onLoginSuccess={vi.fn()} />)
    expect(screen.getByLabelText('Odoo URL')).toBeInTheDocument()
    expect(screen.getByLabelText('Username')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument()
  })

  it('pre-fills the Odoo URL with https://tovarna.es', () => {
    render(<LoginScreen onLoginSuccess={vi.fn()} />)
    expect(screen.getByLabelText('Odoo URL')).toHaveValue('https://tovarna.es')
  })

  it('calls odooLogin with the entered values on submit', async () => {
    mockElectronAPI.odooLogin.mockResolvedValue({ uid: 1, name: 'Javier', sessionId: 'sid', url: 'https://tovarna.es' })
    render(<LoginScreen onLoginSuccess={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'javier@zaratiegui.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret' } })
    fireEvent.click(screen.getByRole('button', { name: 'Login' }))
    await waitFor(() => {
      expect(mockElectronAPI.odooLogin).toHaveBeenCalledWith({
        url: 'https://tovarna.es',
        username: 'javier@zaratiegui.com',
        password: 'secret',
      })
    })
  })

  it('calls onLoginSuccess with session data after successful login', async () => {
    const session = { uid: 1, name: 'Javier', sessionId: 'sid', url: 'https://tovarna.es' }
    mockElectronAPI.odooLogin.mockResolvedValue(session)
    const onLoginSuccess = vi.fn()
    render(<LoginScreen onLoginSuccess={onLoginSuccess} />)
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'j@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'pass' } })
    fireEvent.click(screen.getByRole('button', { name: 'Login' }))
    await waitFor(() => expect(onLoginSuccess).toHaveBeenCalledWith(session))
  })

  it('shows an error message when login fails', async () => {
    mockElectronAPI.odooLogin.mockRejectedValue(new Error('Login failed — check username and password'))
    render(<LoginScreen onLoginSuccess={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'bad@user.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByRole('button', { name: 'Login' }))
    await waitFor(() => screen.getByText('Login failed — check username and password'))
  })

  it('disables the Login button and changes its label while loading', async () => {
    let resolve!: (v: unknown) => void
    mockElectronAPI.odooLogin.mockReturnValue(new Promise(r => { resolve = r }))
    render(<LoginScreen onLoginSuccess={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'u@e.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'p' } })
    fireEvent.click(screen.getByRole('button', { name: 'Login' }))
    expect(screen.getByRole('button', { name: 'Logging in…' })).toBeDisabled()
    resolve({ uid: 1, name: 'J', sessionId: 's', url: 'https://tovarna.es' })
  })
})
