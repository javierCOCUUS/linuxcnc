import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('../../src/renderer/src/hooks/useHalInputs', () => ({
  useHalInputs: vi.fn(),
}))

import { IoInputsPanel } from '../../src/renderer/src/components/panels/IoInputsPanel'
import { useHalInputs } from '../../src/renderer/src/hooks/useHalInputs'

const mockUseHalInputs = vi.mocked(useHalInputs)

const estop = {
  id: '08', pin: 'hm2_7i95.0.inmux.00.input-08', on: true,
  signal: 'remote-estop0', inverted: false, signalOn: true,
}
const limit = {
  id: '10', pin: 'hm2_7i95.0.inmux.00.input-10', on: false,
  signal: 'neg-limit-joint-0', inverted: true, signalOn: true,
}
const spare = {
  id: '03', pin: 'hm2_7i95.0.inmux.00.input-03', on: false,
  signal: null, inverted: false, signalOn: null,
}

beforeEach(() => {
  vi.clearAllMocks()
  mockUseHalInputs.mockReturnValue({ inputs: [estop, limit], error: null, loading: false })
})

describe('IoInputsPanel', () => {
  it('shows a row per input with its physical state', () => {
    render(<IoInputsPanel />)
    expect(screen.getByTestId('io-row-08').textContent).toContain('ON')
    expect(screen.getByTestId('io-row-10').textContent).toContain('OFF')
  })

  it('shows the wired signal and its value', () => {
    render(<IoInputsPanel />)
    expect(screen.getByTestId('io-row-08').textContent).toContain('remote-estop0')
    expect(screen.getByTestId('io-row-08').textContent).toContain('TRUE')
  })

  it('marks signals fed by the inverted pin', () => {
    render(<IoInputsPanel />)
    expect(screen.getByTestId('io-row-10').textContent).toContain('neg-limit-joint-0 (inv)')
  })

  it('says "sin señal" for an input that is not wired', () => {
    mockUseHalInputs.mockReturnValue({ inputs: [spare], error: null, loading: false })
    render(<IoInputsPanel />)
    expect(screen.getByTestId('io-row-03').textContent).toContain('sin señal')
  })

  it('shows a loading message before the first result', () => {
    mockUseHalInputs.mockReturnValue({ inputs: [], error: null, loading: true })
    render(<IoInputsPanel />)
    expect(screen.getByText(/Cargando/)).toBeTruthy()
  })

  it('shows the error when there is nothing to display', () => {
    mockUseHalInputs.mockReturnValue({ inputs: [], error: 'HTTP 403', loading: false })
    render(<IoInputsPanel />)
    expect(screen.getByRole('alert').textContent).toContain('HTTP 403')
  })

  it('keeps showing the last inputs and the error when a later poll fails', () => {
    mockUseHalInputs.mockReturnValue({ inputs: [estop], error: 'timeout', loading: false })
    render(<IoInputsPanel />)
    expect(screen.getByRole('alert').textContent).toContain('timeout')
    expect(screen.getByTestId('io-row-08')).toBeTruthy()
  })

  it('shows an empty message when there are no inputs', () => {
    mockUseHalInputs.mockReturnValue({ inputs: [], error: null, loading: false })
    render(<IoInputsPanel />)
    expect(screen.getByText('No hay entradas')).toBeTruthy()
  })
})
