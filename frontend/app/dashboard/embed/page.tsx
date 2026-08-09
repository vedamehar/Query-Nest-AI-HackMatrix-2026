"use client"

import * as React from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useToast } from "@/components/ui/use-toast"

import { useTenantContext } from "@/lib/tenant-context"

function widgetOrigin(): string {
  const fromEnv = process.env.NEXT_PUBLIC_APP_URL?.replace(/\/+$/, "")
  if (fromEnv) return fromEnv
  if (typeof window !== "undefined") return window.location.origin
  return "http://localhost:3000"
}

export default function EmbedPage() {
  const { activeTenant } = useTenantContext()
  const { toast } = useToast()
  const [copied, setCopied] = React.useState(false)

  const origin = widgetOrigin()
  const apiBase = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || ""
  const snippet = activeTenant
    ? `<script
  src="${origin}/widget.js"
  data-bot-id="${activeTenant.bot_id}"
  data-api="${apiBase}"
  data-primary-color="${activeTenant.primary_color}">
</script>`
    : ""

  const copy = async () => {
    if (!snippet) return
    await navigator.clipboard.writeText(snippet)
    setCopied(true)
    toast.success("Copied to clipboard")
    window.setTimeout(() => setCopied(false), 2000)
  }

  if (!activeTenant) {
    return (
      <div className="py-2">
        <h1 className="text-2xl font-semibold">Embed Your Bot</h1>
        <Alert className="mt-6" variant="destructive">
          <AlertTitle>Select a bot first</AlertTitle>
          <AlertDescription>Choose a bot from the sidebar to view embed instructions.</AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 py-2">
      <div>
        <h1 className="text-2xl font-semibold">Embed Your Bot</h1>
        <p className="text-sm text-muted-foreground">
          Active bot: <span className="font-medium text-foreground">{activeTenant.name}</span> ·{" "}
          <span className="font-mono text-xs">{activeTenant.bot_id}</span>
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Add to any website</CardTitle>
          <CardDescription>
            Paste a short script tag before <span className="font-mono">{"</body>"}</span>. The chat bubble
            loads automatically.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg bg-zinc-950 p-4 text-zinc-50">
            <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs leading-relaxed">
              {snippet}
            </pre>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={() => void copy()}>
              {copied ? "Copied!" : "Copy to Clipboard"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Instructions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>
            <span className="font-medium text-foreground">Step 1:</span> Add your domain to "Allowed Domains" in bot settings.
          </p>
          <p>
            <span className="font-medium text-foreground">Step 2:</span> Copy the embed code code above.
          </p>
          <p>
            <span className="font-medium text-foreground">Step 3:</span> Paste it before{" "}
            <span className="font-mono">{"</body>"}</span> on your website.
          </p>
          <Alert className="border-blue-100 bg-blue-50">
            <ShieldCheck className="h-4 w-4 text-blue-600" />
            <AlertTitle className="text-blue-800">Security Note</AlertTitle>
            <AlertDescription className="text-blue-700 text-xs">
              Your bot is protected by domain whitelisting and session-bound JWTs. 
              Only the websites you explicitly authorize in the "Allowed Domains" list can use this widget.
            </AlertDescription>
          </Alert>
          <Alert className="mt-4">
            <AlertTitle>Widget Initialization</AlertTitle>
            <AlertDescription className="text-xs">
              The widget uses a secure <span className="font-mono">POST /api/widget/init</span> handshake 
              to verify the host domain and issue a private session token.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Widget Preview</CardTitle>
          <CardDescription>Approximate look using your bot branding.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="relative h-[420px] rounded-xl border bg-linear-to-b from-muted/40 to-background p-6">
            <div className="absolute bottom-6 right-6 flex flex-col items-end gap-3">
              <div
                className="h-[340px] w-[320px] overflow-hidden rounded-2xl border bg-white shadow-lg"
                style={{ color: "#0f172a" }}
              >
                <div
                  className="flex items-center gap-3 px-4 py-3 text-white"
                  style={{ backgroundColor: activeTenant.primary_color }}
                >
                  <div className="flex size-9 items-center justify-center rounded-full bg-white/20 text-sm font-bold">
                    🤖
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold">{activeTenant.bot_name}</div>
                    <div className="text-xs opacity-90">Online</div>
                  </div>
                </div>
                <div className="space-y-3 p-4 text-sm">
                  <div className="rounded-2xl bg-slate-100 px-3 py-2 leading-relaxed">
                    {activeTenant.welcome_message}
                  </div>
                  <div className="text-xs text-slate-500">Powered by SiteSense</div>
                </div>
              </div>
              <button
                type="button"
                className="flex size-14 items-center justify-center rounded-full text-white shadow-lg"
                style={{ backgroundColor: activeTenant.primary_color }}
                aria-label="Widget bubble preview"
              >
                💬
              </button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Configuration reference</CardTitle>
          <CardDescription>Optional attributes supported by <span className="font-mono">widget.js</span>.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Attribute</TableHead>
                <TableHead>Purpose</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell className="font-mono text-xs">data-bot-id</TableCell>
                <TableCell>Required. Public bot identifier.</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-mono text-xs">data-api</TableCell>
                <TableCell>FastAPI base URL (default http://localhost:8000).</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-mono text-xs">data-position</TableCell>
                <TableCell>Bubble position: left or right (default right).</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-mono text-xs">data-primary-color</TableCell>
                <TableCell>Optional override; widget still fetches public config from the API.</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
