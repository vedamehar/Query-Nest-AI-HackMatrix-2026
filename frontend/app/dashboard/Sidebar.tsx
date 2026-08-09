"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"

import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import { useTenantContext } from "@/lib/tenant-context"

import { createSupabaseBrowserClient } from "@/lib/supabase-browser"
import { Button } from "@/components/ui/button"
import { 
  BarChart3, 
  Bot, 
  BookText, 
  Code2, 
  LogOut, 
  Settings, 
  Network, 
  PanelLeftClose, 
  PanelLeftOpen 
} from "lucide-react"

const navItems = [
  { label: "🤖 Bots", href: "/dashboard/bots", icon: Bot },
  { label: "📄 Sources", href: "/dashboard/sources", icon: BookText },
  { label: "📊 Analytics", href: "/dashboard/analytics", icon: BarChart3 },
  { label: "🕸️ Network Map", href: "/dashboard/graph", icon: Network },
  { label: "🔗 Embed", href: "/dashboard/embed", icon: Code2 },
  { label: "⚙️ Settings", href: "/dashboard/settings", icon: Settings },
] as const

const NONE_VALUE = "__none__"

interface SidebarProps {
  isCollapsed: boolean
  onToggle: () => void
}

export function DashboardSidebar({ isCollapsed, onToggle }: SidebarProps) {
  const router = useRouter()
  const pathname = usePathname()
  const { tenants, activeTenant, setActiveTenant } = useTenantContext()
  const supabase = createSupabaseBrowserClient()

  const selectValue = activeTenant?.id ?? NONE_VALUE

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    router.push("/login")
  }

  return (
    <aside className={cn(
      "flex shrink-0 flex-col glass border-r border-white/5 py-8 relative z-20 transition-all duration-300 ease-in-out",
      isCollapsed ? "w-20 px-2" : "w-72 px-4"
    )}>
      <div className={cn(
        "mb-8 flex items-center gap-4 px-3 relative",
        isCollapsed ? "justify-center" : "justify-between"
      )}>
        <div className="flex items-center gap-4">
          <div className="size-10 rounded-xl bg-gradient-to-br from-brand-purple to-brand-blue flex items-center justify-center shadow-[0_0_20px_-5px_rgba(139,92,246,0.6)] shrink-0">
            <Bot className="text-white size-6" />
          </div>
          {!isCollapsed && (
            <Link href="/dashboard/bots" className="text-xl font-bold font-heading tracking-tight text-gradient animate-in fade-in duration-300">
              SiteSense
            </Link>
          )}
        </div>
      </div>

      <div className="mb-10 px-2 space-y-4">
        {!isCollapsed && (
          <div className="text-[10px] font-bold tracking-[0.2em] text-muted-foreground uppercase ml-1 opacity-50 animate-in fade-in duration-300">
            Intelligence Node
          </div>
        )}
        
        <Select
          value={selectValue}
          onValueChange={(value) => {
            if (value === "__create_new__") {
              router.push("/dashboard/bots?create=1")
              return
            }
            if (value === NONE_VALUE) return
            const tenant = tenants.find((t) => t.id === value)
            if (tenant) setActiveTenant(tenant)
          }}
        >
          <SelectTrigger className={cn(
            "w-full bg-white/5 border-white/10 h-11 rounded-xl focus:ring-brand-purple/20 transition-all",
            isCollapsed ? "px-0 flex justify-center border-none bg-transparent" : "px-3"
          )}>
             {isCollapsed ? (
               <Bot className="size-5 text-brand-purple" />
             ) : (
               <SelectValue placeholder="Select a bot" />
             )}
          </SelectTrigger>
          <SelectContent className="glass-premium border-white/10 rounded-xl text-white">
            {tenants.length === 0 ? (
              <SelectItem value={NONE_VALUE} disabled>
                No bots yet
              </SelectItem>
            ) : (
              tenants.map((t) => (
                <SelectItem key={t.id} value={t.id} className="focus:bg-brand-purple/20 focus:text-white">
                  {t.name}
                </SelectItem>
              ))
            )}
            <div className="px-2 py-1 text-xs text-muted-foreground">Create new</div>
            <SelectItem value="__create_new__" className="focus:bg-brand-purple/20 focus:text-white">
              Create New Bot
            </SelectItem>
          </SelectContent>
        </Select>

        {activeTenant && !isCollapsed && (
          <div className="mt-3 px-1 animate-in fade-in slide-in-from-left-2 duration-500">
            <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
              <div className="h-full bg-brand-purple w-full shadow-[0_0_10px_rgba(139,92,246,0.5)]" />
            </div>
          </div>
        )}
      </div>

      <nav className="flex flex-col gap-2 px-1">
        {!isCollapsed && (
          <div className="text-[10px] font-bold tracking-[0.2em] text-muted-foreground uppercase mb-2 ml-2 opacity-50 animate-in fade-in duration-300">
            Management
          </div>
        )}
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive =
            item.href === "/dashboard/bots"
              ? pathname.startsWith("/dashboard/bots")
              : pathname === item.href

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-xl py-3 text-sm font-medium transition-all duration-300 group",
                isCollapsed ? "justify-center px-0 w-12 mx-auto" : "px-4 w-full",
                isActive 
                  ? "bg-brand-purple/15 text-brand-purple border border-brand-purple/20 shadow-[0_0_20px_-10px_rgba(139,92,246,0.3)]" 
                  : "text-muted-foreground hover:bg-white/5 hover:text-white"
              )}
              title={isCollapsed ? item.label.replace(/^[^\s]+\s+/, "") : undefined}
            >
              <Icon className={cn("size-5 shrink-0", isActive ? "text-brand-purple" : "text-slate-400 group-hover:text-white transition-colors")} />
              {!isCollapsed && (
                <span className="animate-in fade-in slide-in-from-left-1 duration-300">
                  {item.label.replace(/^[^\s]+\s+/, "")}
                </span>
              )}
            </Link>
          )
        })}
      </nav>

      <div className="mt-auto px-2 pt-6 pb-2 space-y-4">
        <Button 
          variant="ghost" 
          className={cn(
            "w-full justify-start text-muted-foreground hover:text-red-400 hover:bg-red-400/10 h-12 rounded-xl transition-all",
            isCollapsed ? "px-0 justify-center h-10 w-10 mx-auto" : "px-4"
          )}
          onClick={handleSignOut}
          title={isCollapsed ? "Sign Out" : undefined}
        >
          <LogOut className={cn("h-4 w-4 shrink-0", !isCollapsed && "mr-3")} />
          {!isCollapsed && <span className="font-heading">SIGN OUT</span>}
        </Button>
        
        {!isCollapsed && (
          <div className="flex items-center justify-between px-2 text-[10px] font-bold tracking-widest text-muted-foreground opacity-30 animate-in fade-in duration-300">
            <span>SITESENSE AI</span>
            <span>V2.0</span>
          </div>
        )}

        <button 
          onClick={onToggle}
          className="absolute -right-3 top-20 size-6 rounded-full bg-brand-purple flex items-center justify-center text-white shadow-lg border border-white/10 hover:scale-110 transition-transform z-30"
        >
          {isCollapsed ? <PanelLeftOpen className="size-3" /> : <PanelLeftClose className="size-3" />}
        </button>
      </div>
    </aside>
  )
}
