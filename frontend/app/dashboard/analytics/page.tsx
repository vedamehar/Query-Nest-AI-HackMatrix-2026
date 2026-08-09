"use client"

import * as React from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { Loader2, MessageSquare, Percent, Sun, XCircle, Zap, Cpu } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"

import {
  getAnalytics,
  getConversations,
  getUnanswered,
  type AnalyticsData,
  type Conversation,
} from "@/lib/api"
import { useTenantContext } from "@/lib/tenant-context"

function truncate(s: string, n: number) {
  const t = s.trim()
  if (t.length <= n) return t
  return `${t.slice(0, n - 1)}…`
}

function confidenceBadgeVariant(conf: string): "default" | "secondary" | "destructive" | "outline" {
  const c = conf.toLowerCase()
  if (c === "high") return "default"
  if (c === "medium") return "secondary"
  return "outline"
}

export default function AnalyticsPage() {
  const { activeTenant } = useTenantContext()
  const [summary, setSummary] = React.useState<AnalyticsData | null>(null)
  const [unanswered, setUnanswered] = React.useState<Conversation[]>([])
  const [recent, setRecent] = React.useState<Conversation[]>([])
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!activeTenant) return
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const [a, u, c] = await Promise.all([
          getAnalytics(activeTenant.id),
          getUnanswered(activeTenant.id),
          getConversations(activeTenant.id, 50),
        ])
        if (!cancelled) {
          setSummary(a)
          setUnanswered(u)
          setRecent(c)
        }
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load analytics")
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [activeTenant])

  if (!activeTenant) {
    return (
      <div className="py-2">
        <h1 className="text-2xl font-semibold">Analytics</h1>
        <Alert className="mt-6" variant="destructive">
          <AlertTitle>Select a bot first</AlertTitle>
          <AlertDescription>Choose a bot from the sidebar to view analytics.</AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 py-2">
      <div>
        <h1 className="text-2xl font-semibold">Analytics</h1>
        <p className="text-sm text-muted-foreground">
          Conversation insights for <span className="font-medium text-foreground">{activeTenant.name}</span>
        </p>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Could not load analytics</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {loading && !summary ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      ) : summary ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Conversations</CardTitle>
              <MessageSquare className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold">{summary.total_conversations}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Answer Rate</CardTitle>
              <Percent className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold">{summary.answer_rate}%</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Conversations Today</CardTitle>
              <Sun className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold">{summary.conversations_today}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Unanswered Questions</CardTitle>
              <XCircle className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className={cn("text-2xl font-semibold", summary.unanswered_count > 0 && "text-destructive")}>
                {summary.unanswered_count}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Tokens Used</CardTitle>
              <Zap className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold">{summary.total_tokens.toLocaleString()}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Provider</CardTitle>
              <Cpu className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold capitalize">{summary.top_provider}</div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Daily Conversations</CardTitle>
          <CardDescription>Last 7 days</CardDescription>
        </CardHeader>
        <CardContent className="h-[320px]">
          {summary ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={summary.daily_counts}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#2563eb" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              <Loader2 className="mr-2 size-4 animate-spin" />
              Loading chart…
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Knowledge Gaps</CardTitle>
          <CardDescription>Questions the bot could not answer</CardDescription>
        </CardHeader>
        <CardContent>
          {unanswered.length === 0 ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              🎉 All questions answered!
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Question</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Session</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {unanswered.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="max-w-[420px] whitespace-normal">{row.question}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(row.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{row.session_id}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Conversations</CardTitle>
          <CardDescription>Latest messages logged for this bot</CardDescription>
        </CardHeader>
        <CardContent>
          {recent.length === 0 ? (
            <div className="py-10 text-center text-sm text-muted-foreground">No conversations yet.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Question</TableHead>
                  <TableHead>Answer Preview</TableHead>
                  <TableHead>Answered</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recent.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="max-w-[260px] whitespace-normal">{row.question}</TableCell>
                    <TableCell className="max-w-[320px] whitespace-normal text-muted-foreground">
                      {truncate(row.answer, 80)}
                    </TableCell>
                    <TableCell>{row.was_answered ? "✅" : "❌"}</TableCell>
                    <TableCell>
                      <Badge variant={confidenceBadgeVariant(row.confidence)} className="capitalize">
                        {row.confidence}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(row.created_at).toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
