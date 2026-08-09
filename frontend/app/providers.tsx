"use client"

import * as React from "react"
import { ThemeProvider } from "next-themes"

import { Toaster } from "@/components/ui/sonner"
import { TenantProvider } from "@/lib/tenant-context"

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      enableColorScheme={false}
      disableTransitionOnChange
    >
      <TenantProvider>
        <Toaster richColors />
        {children}
      </TenantProvider>
    </ThemeProvider>
  )
}

