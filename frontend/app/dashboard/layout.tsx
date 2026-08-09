"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

import { Breadcrumbs } from "./Breadcrumbs"
import { DashboardSidebar } from "./Sidebar"

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  const [isCollapsed, setIsCollapsed] = React.useState(false)

  return (
    <div className="min-h-screen flex aurora-bg selection:bg-brand-purple/30">
      <DashboardSidebar isCollapsed={isCollapsed} onToggle={() => setIsCollapsed(!isCollapsed)} />
      <div className={cn(
        "flex-1 flex flex-col relative z-10 w-full overflow-hidden transition-all duration-300 ease-in-out",
        isCollapsed ? "pl-2" : "pl-0"
      )}>
        <div className="px-8 pt-6 pb-2">
          <Breadcrumbs />
        </div>
        <main className="flex-1 px-8 pb-12 overflow-y-auto w-full">{children}</main>
      </div>
    </div>
  )
}

