"use client"

import * as React from "react"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { Loader2, RefreshCw, Trash2, Upload } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useToast } from "@/components/ui/use-toast"

import { deleteSource, getSources, ingestFile, ingestUrl, reindexSource, type Source } from "@/lib/api"
import { useTenantContext } from "@/lib/tenant-context"

const urlSchema = z.object({
  url: z.string().url("Enter a valid URL"),
  name: z.string().optional(),
})

type UrlForm = z.infer<typeof urlSchema>

function SourceStatusBadge({ status }: { status: string }) {
  const s = status.toLowerCase()
  if (s === "pending") {
    return (
      <Badge variant="secondary" className="bg-muted text-muted-foreground">
        Pending
      </Badge>
    )
  }
  if (s === "indexing") {
    return (
      <Badge variant="secondary" className="border border-amber-300/60 bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
        <Loader2 className="size-3 animate-spin" />
        Indexing...
      </Badge>
    )
  }
  if (s === "indexed") {
    return (
      <Badge className="bg-emerald-600 text-white hover:bg-emerald-600/90">Indexed</Badge>
    )
  }
  if (s === "failed") {
    return <Badge variant="destructive">Failed</Badge>
  }
  return <Badge variant="outline">{status}</Badge>
}

function TypeBadge({ type }: { type: string }) {
  const t = type.toLowerCase()
  if (t === "url") return <Badge variant="outline">🌐 Website</Badge>
  if (t === "pdf") return <Badge variant="outline">📄 PDF</Badge>
  if (t === "txt" || t === "text") return <Badge variant="outline">📝 Text</Badge>
  if (t === "md" || t === "markdown") return <Badge variant="outline">📝 Markdown</Badge>
  if (t === "csv") return <Badge variant="outline">📊 CSV</Badge>
  if (t === "excel" || t === "xlsx" || t === "xls") return <Badge variant="outline">📊 Excel</Badge>
  return <Badge variant="outline">{type}</Badge>
}

export default function SourcesPage() {
  const { activeTenant } = useTenantContext()
  const { toast } = useToast()

  const [sources, setSources] = React.useState<Source[]>([])
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [urlBusy, setUrlBusy] = React.useState(false)
  const [fileBusy, setFileBusy] = React.useState(false)
  const [fileInput, setFileInput] = React.useState<File | null>(null)
  const [fileName, setFileName] = React.useState("")
  const [dragOver, setDragOver] = React.useState(false)
  const [deleteTarget, setDeleteTarget] = React.useState<Source | null>(null)

  const loadSources = React.useCallback(async () => {
    if (!activeTenant) return
    setLoading(true)
    setError(null)
    try {
      const list = await getSources(activeTenant.id)
      setSources(list)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load sources")
    } finally {
      setLoading(false)
    }
  }, [activeTenant])

  React.useEffect(() => {
    void loadSources()
  }, [loadSources])

  const needsPolling = sources.some((s) => {
    const st = s.status.toLowerCase()
    return st === "pending" || st === "indexing"
  })

  React.useEffect(() => {
    if (!activeTenant || !needsPolling) return
    const id = window.setInterval(() => {
      void loadSources()
    }, 3000)
    return () => window.clearInterval(id)
  }, [activeTenant, needsPolling, loadSources])

  const urlForm = useForm<UrlForm>({
    resolver: zodResolver(urlSchema),
    defaultValues: { url: "", name: "" },
  })

  if (!activeTenant) {
    return (
      <div className="py-2">
        <h1 className="text-2xl font-semibold">Knowledge Sources</h1>
        <p className="text-sm text-muted-foreground">Content your bot learns from</p>
        <Alert className="mt-6" variant="destructive">
          <AlertTitle>Select a bot first</AlertTitle>
          <AlertDescription>Choose a bot from the sidebar, or create one under Bots.</AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 py-2">
      <div>
        <h1 className="text-2xl font-semibold">Knowledge Sources</h1>
        <p className="text-sm text-muted-foreground">
          Content your bot learns from · <span className="font-medium text-foreground">{activeTenant.name}</span>
        </p>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Could not load sources</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Add website</CardTitle>
            <CardDescription>Ingest content from a public URL.</CardDescription>
          </CardHeader>
          <CardContent>
            <Form
              form={urlForm}
              onSubmit={async (values) => {
                setUrlBusy(true)
                try {
                  await ingestUrl(
                    activeTenant.id,
                    values.url.trim(),
                    values.name?.trim() ? values.name.trim() : undefined
                  )
                  urlForm.reset({ url: "", name: "" })
                  await loadSources()
                  toast.success("Website queued for indexing")
                } catch (e: unknown) {
                  toast.error(e instanceof Error ? e.message : "Failed to add website")
                } finally {
                  setUrlBusy(false)
                }
              }}
            >
              <FormField
                control={urlForm.control}
                name="url"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Website URL</FormLabel>
                    <FormControl>
                      <Input placeholder="https://example.com/docs" {...field} />
                    </FormControl>
                    <FormMessage name="url" />
                  </FormItem>
                )}
              />
              <FormField
                control={urlForm.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Source name (optional)</FormLabel>
                    <FormControl>
                      <Input placeholder="Marketing site" {...field} />
                    </FormControl>
                  </FormItem>
                )}
              />
              <div className="mt-4 flex justify-end">
                <Button type="submit" disabled={urlBusy}>
                  {urlBusy ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      Adding…
                    </>
                  ) : (
                    "Add Website"
                  )}
                </Button>
              </div>
            </Form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Upload File</CardTitle>
            <CardDescription>Upload PDF, TXT, MD, CSV, or Excel files.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              className={[
                "flex min-h-[140px] cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-6 text-center text-sm transition-colors",
                dragOver ? "border-primary bg-primary/5" : "border-border",
              ].join(" ")}
              onDragOver={(e) => {
                e.preventDefault()
                setDragOver(true)
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragOver(false)
                const f = e.dataTransfer.files?.[0]
                const allowed = [
                  "application/pdf", 
                  "text/plain", 
                  "text/markdown", 
                  "text/csv",
                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                  "application/vnd.ms-excel"
                ]
                if (f && (allowed.includes(f.type) || f.name.endsWith('.md') || f.name.endsWith('.csv'))) setFileInput(f)
                else toast.error("Unsupported file type. Use PDF, TXT, MD, CSV, or Excel.")
              }}
              onClick={() => document.getElementById("file-input")?.click()}
              role="button"
              tabIndex={0}
              >
              <Upload className="size-6 text-muted-foreground" />
              <div className="font-medium">{fileInput ? fileInput.name : "Drop file here or click to upload"}</div>
              <div className="text-xs text-muted-foreground">PDF, TXT, MD, CSV, Excel (Max 50 MB)</div>
              <input
                id="file-input"
                type="file"
                accept=".pdf,.txt,.md,.csv,text/plain,text/markdown,text/csv,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null
                  setFileInput(f)
                }}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="file-custom-name">
                Custom name (optional)
              </label>
              <Input
                id="file-custom-name"
                value={fileName}
                onChange={(e) => setFileName(e.target.value)}
                placeholder="Knowledge source name"
              />
            </div>

            <div className="flex justify-end">
              <Button
                type="button"
                disabled={fileBusy || !fileInput}
                onClick={async () => {
                  if (!fileInput || !activeTenant) return
                  setFileBusy(true)
                  try {
                    await ingestFile(
                      activeTenant.id,
                      fileInput,
                      fileName.trim() ? fileName.trim() : undefined
                    )
                    setFileInput(null)
                    setFileName("")
                    await loadSources()
                    toast.success("File queued for indexing")
                  } catch (e: unknown) {
                    toast.error(e instanceof Error ? e.message : "Failed to upload file")
                  } finally {
                    setFileBusy(false)
                  }
                }}
              >
                {fileBusy ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    Uploading…
                  </>
                ) : (
                  "Upload File"
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Sources</CardTitle>
          <CardDescription>Indexing status and chunk counts per source.</CardDescription>
        </CardHeader>
        <CardContent>
          {loading && sources.length === 0 ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : sources.length === 0 ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              No sources yet. Add a website URL or upload a file (PDF, TXT, MD, CSV, Excel).
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Chunks</TableHead>
                  <TableHead>Last Indexed</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sources.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="max-w-[220px] truncate font-medium">{s.name}</TableCell>
                    <TableCell>
                      <TypeBadge type={s.type} />
                    </TableCell>
                    <TableCell>
                      <SourceStatusBadge status={s.status} />
                    </TableCell>
                    <TableCell>{s.chunk_count}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {s.last_indexed ? new Date(s.last_indexed).toLocaleString() : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="icon-sm"
                          aria-label="Re-index"
                          onClick={async () => {
                            try {
                              await reindexSource(s.id)
                              await loadSources()
                              toast.success("Re-index started")
                            } catch (e: unknown) {
                              toast.error(e instanceof Error ? e.message : "Re-index failed")
                            }
                          }}
                        >
                          <RefreshCw className="size-4" />
                        </Button>
                        <Button
                          type="button"
                          variant="destructive"
                          size="icon-sm"
                          aria-label="Delete source"
                          onClick={() => setDeleteTarget(s)}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete source</DialogTitle>
            <DialogDescription>
              This removes the source record and deletes its vectors from Chroma.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button type="button" variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={async () => {
                if (!deleteTarget) return
                try {
                  await deleteSource(deleteTarget.id)
                  setDeleteTarget(null)
                  await loadSources()
                  toast.success("Source deleted")
                } catch (e: unknown) {
                  toast.error(e instanceof Error ? e.message : "Delete failed")
                }
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
