"use client"

import * as React from "react"
import { Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Bot, Copy, Plus, Trash2, AlertTriangle } from "lucide-react"

import { Skeleton } from "@/components/ui/skeleton"

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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import { useToast } from "@/components/ui/use-toast"

import { createTenant, deleteTenant, updateTenant, type Tenant } from "@/lib/api"
import { useTenantContext } from "@/lib/tenant-context"

const SUGGESTED_MIN = 3

const tenantSchema = z.object({
  name: z.string().min(1, "Bot Display Name is required"),
  bot_name: z.string().min(1, "Assistant Name is required"),
  welcome_message: z.string().optional(),
  fallback_message: z.string().optional(),
  primary_color: z
    .string()
    .regex(/^#([0-9a-fA-F]{6})$/, "Primary Color must be a hex value like #2563eb"),
  system_prompt: z.string().optional().or(z.literal("")),
  llm_provider: z.string().min(1, "AI Provider is required"),
  llm_model: z.string().min(1, "LLM Model is required"),
  suggested_questions: z.array(z.string()),
  allowed_origins: z.array(z.string()),
})

type TenantFormValues = {
  name: string
  bot_name: string
  welcome_message?: string
  fallback_message?: string
  primary_color: string
  system_prompt?: string
  llm_provider: string
  llm_model: string
  suggested_questions: string[]
  allowed_origins: string[]
}

const PROVIDER_OPTIONS = [
  { label: "Anthropic (Claude)", value: "claude" },
  { label: "Google (Gemini)", value: "gemini" },
]

const MODEL_OPTIONS: Record<string, { label: string; value: string }[]> = {
  claude: [
    { label: "Claude 3.5 Sonnet", value: "claude-3-5-sonnet-20241022" },
    { label: "Claude 3.5 Haiku", value: "claude-3-5-haiku-20241022" },
  ],
  gemini: [
    { label: "Gemini 2.0 Flash", value: "gemini-2.0-flash" },
    { label: "Gemini 2.5 Flash", value: "gemini-2.5-flash" },
    { label: "Gemini 2.5 Pro", value: "gemini-2.5-pro" },
  ],
}

function normalizeStringList(list: string[] | undefined, minLen: number): string[] {
  const safe = (list ?? []).map((s) => String(s ?? ""))
  const padded = safe.slice()
  while (padded.length < minLen) padded.push("")
  return padded
}

function filterNonEmpty(list: string[]): string[] {
  return list.map((s) => s.trim()).filter((s) => s.length > 0)
}

function BotsPageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { tenants, refreshTenants, setActiveTenant } = useTenantContext()
  const { toast } = useToast()

  const createParam = searchParams.get("create")

  const [createOpen, setCreateOpen] = React.useState(false)
  const [editOpen, setEditOpen] = React.useState(false)
  const [editingTenant, setEditingTenant] = React.useState<Tenant | null>(null)
  const [deleteTarget, setDeleteTarget] = React.useState<Tenant | null>(null)

  React.useEffect(() => {
    if (createParam === "1") setCreateOpen(true)
  }, [createParam])

  const handleCopyBotId = async (botId: string) => {
    await navigator.clipboard.writeText(botId)
    toast.success("Bot ID copied")
  }

  const closeCreate = () => {
    setCreateOpen(false)
    router.replace("/dashboard/bots")
  }

  return (
    <div className="flex flex-col gap-6 py-2">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Your Bots</h1>
          <p className="text-sm text-muted-foreground">
            Manage your AI chatbot configurations
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" />
          Create New Bot
        </Button>
      </div>

      {tenants.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
          <div className="flex size-16 items-center justify-center rounded-full bg-primary/10">
            <Bot className="size-8 text-primary" />
          </div>
          <div>
            <div className="text-lg font-medium">No bots yet</div>
            <p className="mt-1 text-sm text-muted-foreground">
              Create your first bot to start ingesting knowledge and answering questions.
            </p>
          </div>
          <Button onClick={() => setCreateOpen(true)}>Create your first bot</Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {tenants.map((t) => (
            <Card key={t.id}>
              <CardHeader className="pb-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div
                      className="mt-2 size-3 shrink-0 rounded-full"
                      style={{ backgroundColor: t.primary_color }}
                    />
                    <div>
                      <CardTitle className="text-base">{t.name}</CardTitle>
                      <CardDescription className="mt-1 flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs text-muted-foreground">{t.bot_id}</span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-xs"
                          onClick={() => handleCopyBotId(t.bot_id)}
                          aria-label="Copy bot id"
                        >
                          <Copy className="size-4" />
                        </Button>
                      </CardDescription>
                    </div>
                  </div>
                  <div className="whitespace-nowrap text-xs text-muted-foreground">
                    Created {new Date(t.created_at).toLocaleDateString()}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <Badge variant="outline" className="w-fit font-mono text-xs">
                  {t.bot_id}
                </Badge>
                <Separator />
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setEditingTenant(t)
                        setEditOpen(true)
                      }}
                    >
                      Edit
                    </Button>
                    <Button type="button" variant="destructive" onClick={() => setDeleteTarget(t)}>
                      Delete
                    </Button>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => {
                        setActiveTenant(t)
                        router.push("/dashboard/sources")
                      }}
                    >
                      View Sources
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => {
                        setActiveTenant(t)
                        router.push("/dashboard/embed")
                      }}
                    >
                      Get Embed Code
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <TenantDialog
        open={createOpen}
        mode="create"
        tenant={null}
        onOpenChange={(o) => (o ? setCreateOpen(true) : closeCreate())}
        onSuccess={async () => {
          await refreshTenants()
          closeCreate()
          toast.success("Bot created successfully")
        }}
      />

      <TenantDialog
        open={editOpen}
        mode="edit"
        tenant={editingTenant}
        onOpenChange={(o) => {
          setEditOpen(o)
          if (!o) setEditingTenant(null)
        }}
        onSuccess={async () => {
          await refreshTenants()
          setEditOpen(false)
          setEditingTenant(null)
          toast.success("Bot updated successfully")
        }}
      />

      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete bot</DialogTitle>
            <DialogDescription>
              This will delete the bot and all related sources, conversations, and leads.
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
                  await deleteTenant(deleteTarget.id)
                  setDeleteTarget(null)
                  await refreshTenants()
                  toast.success("Bot deleted")
                } catch (e: unknown) {
                  toast.error(e instanceof Error ? e.message : "Failed to delete bot")
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

export default function BotsPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-4 py-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-40 w-full" />
        </div>
      }
    >
      <BotsPageInner />
    </Suspense>
  )
}

function TenantDialog({
  open,
  mode,
  tenant,
  onOpenChange,
  onSuccess,
}: {
  open: boolean
  mode: "create" | "edit"
  tenant: Tenant | null
  onOpenChange: (open: boolean) => void
  onSuccess: () => Promise<void>
}) {
  const { toast } = useToast()

  const form = useForm<TenantFormValues>({
    resolver: zodResolver(tenantSchema),
    defaultValues: {
      name: "",
      bot_name: "",
      welcome_message: "Hi! How can I help you?",
      fallback_message: "I don't have information on that topic.",
      primary_color: "#2563eb",
      system_prompt: "",
      llm_provider: "gemini",
      llm_model: "gemini-2.0-flash",
      suggested_questions: ["", "", ""],
      allowed_origins: [""],
    },
  })

  const { control, watch, setValue, reset, getValues } = form
  const primaryColor = watch("primary_color")
  const suggestedQuestions = watch("suggested_questions")
  const allowedOriginsWatch = watch("allowed_origins")
  const selectedProvider = watch("llm_provider")

  const nonEmptyOrigins = filterNonEmpty(allowedOriginsWatch)
  const showWarning = nonEmptyOrigins.length === 0

  React.useEffect(() => {
    if (!open) return
    if (mode === "edit" && tenant) {
      reset({
        name: tenant.name ?? "",
        bot_name: tenant.bot_name ?? "",
        welcome_message: tenant.welcome_message ?? "",
        fallback_message: tenant.fallback_message ?? "",
        primary_color: tenant.primary_color ?? "#2563eb",
        system_prompt: tenant.system_prompt ?? "",
        llm_provider: tenant.llm_provider ?? "gemini",
        llm_model: tenant.llm_model ?? "gemini-2.0-flash",
        suggested_questions: normalizeStringList(tenant.suggested_questions ?? [], SUGGESTED_MIN),
        allowed_origins: tenant.allowed_origins?.length ? tenant.allowed_origins : [""],
      })
    }
    if (mode === "create") {
      reset({
        name: "",
        bot_name: "",
        welcome_message: "Hi! How can I help you?",
        fallback_message: "I don't have information on that topic.",
        primary_color: "#2563eb",
        system_prompt: "",
        llm_provider: "gemini",
        llm_model: "gemini-2.0-flash",
        suggested_questions: ["", "", ""],
        allowed_origins: [""],
      })
    }
  }, [open, mode, tenant, reset])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{mode === "create" ? "Create Bot" : "Edit Bot"}</DialogTitle>
          <DialogDescription>
            Configure the bot identity, onboarding messages, and knowledge access rules.
          </DialogDescription>
        </DialogHeader>

        <Form
          form={form}
          onSubmit={async (values) => {
            const allowed_origins = filterNonEmpty(values.allowed_origins)
            const suggested_questions = filterNonEmpty(values.suggested_questions)
            const payload = {
              name: values.name.trim(),
              bot_name: values.bot_name.trim(),
              welcome_message: values.welcome_message ?? "",
              fallback_message: values.fallback_message ?? "",
              primary_color: values.primary_color,
              system_prompt: values.system_prompt ?? "",
              llm_provider: values.llm_provider,
              llm_model: values.llm_model,
              allowed_origins,
              suggested_questions,
            }
            try {
              if (mode === "create") await createTenant(payload)
              else {
                if (!tenant) throw new Error("No tenant selected")
                await updateTenant(tenant.id, payload)
              }
              await onSuccess()
            } catch (e: unknown) {
              toast.error(e instanceof Error ? e.message : "Failed to save bot")
            }
          }}
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField
              control={control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Bot Display Name (your website name)</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage name="name" />
                </FormItem>
              )}
            />
            <FormField
              control={control}
              name="bot_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Assistant Name (what users see)</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage name="bot_name" />
                </FormItem>
              )}
            />
          </div>

          <FormField
            control={control}
            name="welcome_message"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Welcome Message</FormLabel>
                <FormControl>
                  <Textarea {...field} />
                </FormControl>
              </FormItem>
            )}
          />

          <FormField
            control={control}
            name="fallback_message"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Fallback Message</FormLabel>
                <FormControl>
                  <Textarea {...field} />
                </FormControl>
              </FormItem>
            )}
          />

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 md:items-end">
            <FormField
              control={control}
              name="primary_color"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Primary Color</FormLabel>
                  <div className="flex items-center gap-3">
                    <input
                      type="color"
                      value={primaryColor}
                      onChange={(e) =>
                        setValue("primary_color", e.target.value, { shouldValidate: true })
                      }
                      className="h-10 w-12 rounded-md border border-input bg-background"
                      aria-label="Primary color picker"
                    />
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                  </div>
                  <FormMessage name="primary_color" />
                  <p className="text-xs text-muted-foreground">Hex like #2563eb</p>
                </FormItem>
              )}
            />
            <FormField
              control={control}
              name="system_prompt"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>System Prompt (optional)</FormLabel>
                  <FormControl>
                    <Textarea {...field} />
                  </FormControl>
                </FormItem>
              )}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FormField
              control={control}
              name="llm_provider"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>AI Provider</FormLabel>
                  <Select
                    onValueChange={(val: string | null) => {
                      if (!val) return;
                      field.onChange(val)
                      const firstModel = MODEL_OPTIONS[val]?.[0]?.value || ""
                      setValue("llm_model", firstModel)
                    }}
                    defaultValue={field.value}
                    value={field.value}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select a provider" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {PROVIDER_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage name="llm_provider" />
                </FormItem>
              )}
            />
            <FormField
              control={control}
              name="llm_model"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Model</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    defaultValue={field.value}
                    value={field.value}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select a model" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {(MODEL_OPTIONS[selectedProvider as keyof typeof MODEL_OPTIONS] ?? []).map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage name="llm_model" />
                </FormItem>
              )}
            />
          </div>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div>
              <div className="mb-2 flex items-center justify-between gap-2">
                <div>
                  <div className="text-sm font-medium">Suggested Questions</div>
                  <p className="text-xs text-muted-foreground">Add or remove starter questions.</p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setValue("suggested_questions", [...getValues("suggested_questions"), ""])
                  }
                >
                  Add
                </Button>
              </div>
              <div className="flex flex-col gap-2">
                {suggestedQuestions.map((_, idx) => (
                  <div key={`sq-${idx}`} className="flex items-start gap-2">
                    <FormField
                      control={control}
                      name={`suggested_questions.${idx}`}
                      render={({ field }) => (
                        <FormItem className="flex-1">
                          <FormControl>
                            <Input {...field} placeholder={`Question ${idx + 1}`} />
                          </FormControl>
                          <FormMessage name={`suggested_questions.${idx}`} />
                        </FormItem>
                      )}
                    />
                    {idx >= SUGGESTED_MIN ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        aria-label="Remove suggested question"
                        onClick={() =>
                          setValue(
                            "suggested_questions",
                            getValues("suggested_questions").filter((_, i) => i !== idx)
                          )
                        }
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    ) : (
                      <span className="w-8 shrink-0" />
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between gap-2">
                <div>
                  <div className="text-sm font-medium">Allowed Origins</div>
                  <p className="text-xs text-muted-foreground">
                    Domain whitelist. Empty list means allow all.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setValue("allowed_origins", [...getValues("allowed_origins"), ""])
                  }
                >
                  Add
                </Button>
              </div>
              <div className="flex flex-col gap-2">
                {allowedOriginsWatch.map((_, idx) => (
                  <div key={`ao-${idx}`} className="flex items-start gap-2">
                    <FormField
                      control={control}
                      name={`allowed_origins.${idx}`}
                      render={({ field }) => (
                        <FormItem className="flex-1">
                          <FormControl>
                            <Input
                              {...field}
                              placeholder={idx === 0 ? "https://mysite.com" : `Origin ${idx + 1}`}
                            />
                          </FormControl>
                          <FormMessage name={`allowed_origins.${idx}`} />
                        </FormItem>
                      )}
                    />
                    {allowedOriginsWatch.length > 1 ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        aria-label="Remove allowed origin"
                        onClick={() =>
                          setValue(
                            "allowed_origins",
                            getValues("allowed_origins").filter((_, i) => i !== idx)
                          )
                        }
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    ) : (
                      <span className="w-8 shrink-0" />
                    )}
                  </div>
                ))}
              </div>
              
              {showWarning && (
                <Alert className="mt-4 border-amber-200 bg-amber-50">
                  <AlertTriangle className="size-4 text-amber-600" />
                  <AlertTitle className="text-amber-800">Security Requirement</AlertTitle>
                  <AlertDescription className="text-xs text-amber-700">
                    Add your website domain to prevent unauthorized widget usage. e.g. https://mysite.com
                  </AlertDescription>
                </Alert>
              )}
            </div>
          </div>

          <DialogFooter className="mt-6 gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit">{mode === "create" ? "Create Bot" : "Save Changes"}</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
