"use client"

import * as React from "react"
import { getTenants, type Tenant } from "@/lib/api"

type TenantContextValue = {
  activeTenant: Tenant | null
  setActiveTenant: (t: Tenant) => void
  tenants: Tenant[]
  setTenants: (t: Tenant[]) => void
  refreshTenants: () => Promise<void>
}

const TenantContext = React.createContext<TenantContextValue | null>(null)

export function useTenantContext(): TenantContextValue {
  const ctx = React.useContext(TenantContext)
  if (!ctx) throw new Error("useTenantContext must be used within TenantProvider")
  return ctx
}

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const [tenants, setTenants] = React.useState<Tenant[]>([])
  const [activeTenant, setActiveTenantState] = React.useState<Tenant | null>(null)

  const setActiveTenant = React.useCallback((t: Tenant) => {
    setActiveTenantState(t)
  }, [])

  const refreshTenants = React.useCallback(async () => {
    const list = await getTenants()
    setTenants(list)

    setActiveTenantState((prev) => {
      // Preserve the currently selected tenant if it still exists.
      if (prev && list.some((t) => t.id === prev.id)) return prev
      return list[0] ?? null
    })
  }, [])

  React.useEffect(() => {
    // Load tenants once on mount.
    refreshTenants().catch(() => {
      // Stage 1: no auth. On failure keep the app usable with empty state.
      setTenants([])
      setActiveTenantState(null)
    })
    
    // Listen to Supabase auth state changes to clear/refresh tenants properly
    const { createSupabaseBrowserClient } = require("@/lib/supabase-browser")
    const supabase = createSupabaseBrowserClient()
    const { data: authListener } = supabase.auth.onAuthStateChange(
      (event: string, session: any) => {
        if (event === "SIGNED_OUT") {
          setTenants([])
          setActiveTenantState(null)
        } else if (event === "SIGNED_IN") {
          refreshTenants().catch(console.error)
        }
      }
    )

    return () => {
      authListener.subscription.unsubscribe()
    }
  }, [refreshTenants])

  const value = React.useMemo<TenantContextValue>(
    () => ({
      activeTenant,
      setActiveTenant,
      tenants,
      setTenants,
      refreshTenants,
    }),
    [activeTenant, setActiveTenant, tenants, refreshTenants]
  )

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>
}

