import { useState, useEffect } from 'react'
import { LoginScreen } from './components/LoginScreen'
import { AppShell } from './components/AppShell'
import type { OdooSession } from './types/electron-api'

type AppState =
  | { status: 'checking' }
  | { status: 'login' }
  | { status: 'authenticated'; session: OdooSession }

export function App(): JSX.Element {
  const [state, setState] = useState<AppState>({ status: 'checking' })

  useEffect(() => {
    window.electronAPI.getSession().then(session => {
      if (session) {
        setState({ status: 'authenticated', session })
      } else {
        setState({ status: 'login' })
      }
    })
  }, [])

  if (state.status === 'checking') {
    return <div className="app-checking">Loading…</div>
  }

  if (state.status === 'login') {
    return (
      <LoginScreen
        onLoginSuccess={session => setState({ status: 'authenticated', session })}
      />
    )
  }

  return (
    <AppShell
      userId={String(state.session.uid)}
      userName={state.session.name}
      onLogout={() => setState({ status: 'login' })}
    />
  )
}
