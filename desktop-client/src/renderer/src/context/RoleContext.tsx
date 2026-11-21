import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

export type Role = 'machine' | 'operator'

// Without a provider (tests, isolated panels) the role is "machine": nothing is disabled.
const RoleContext = createContext<Role>('machine')

/**
 * Asks the backend which role the stored token has. Until it answers the role is
 * "operator", so the controls that move the machine stay disabled; if the backend cannot
 * be reached it stays that way.
 */
export function RoleProvider({ children }: { children: ReactNode }): JSX.Element {
  const [role, setRole] = useState<Role>('operator')

  useEffect(() => {
    let mounted = true
    window.electronAPI.getRole()
      .then(result => { if (mounted) setRole(result.role) })
      .catch(() => { /* stays "operator" */ })
    return () => { mounted = false }
  }, [])

  return <RoleContext.Provider value={role}>{children}</RoleContext.Provider>
}

export function useRole(): Role {
  return useContext(RoleContext)
}
