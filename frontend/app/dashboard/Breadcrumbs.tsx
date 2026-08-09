"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { Separator } from "@/components/ui/separator"

type Crumb = { label: string; href: string }

function labelForSegment(segment: string): string {
  switch (segment) {
    case "bots":
      return "Bots"
    case "sources":
      return "Sources"
    case "analytics":
      return "Analytics"
    case "embed":
      return "Embed"
    default:
      return segment
  }
}

export function Breadcrumbs() {
  const pathname = usePathname()
  const parts = pathname.split("/").filter(Boolean)

  if (parts.length < 1 || parts[0] !== "dashboard") return null

  const crumbs: Crumb[] = [{ label: "Dashboard", href: "/dashboard/bots" }]

  const sub = parts.slice(1)
  for (let i = 0; i < sub.length; i++) {
    const segment = sub[i]
    const href = "/dashboard/" + sub.slice(0, i + 1).join("/")
    crumbs.push({ label: labelForSegment(segment), href })
  }

  return (
    <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-sm">
      {crumbs.map((c, idx) => {
        const isLast = idx === crumbs.length - 1
        return (
          <span key={`${c.href}-${idx}`} className="flex items-center gap-2">
            {isLast ? (
              <span className="text-foreground">{c.label}</span>
            ) : (
              <Link href={c.href} className="text-muted-foreground hover:text-foreground">
                {c.label}
              </Link>
            )}
            {!isLast && <Separator orientation="vertical" className="h-4" />}
          </span>
        )
      })}
    </nav>
  )
}
