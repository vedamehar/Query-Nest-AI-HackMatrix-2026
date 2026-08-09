"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { 
  Zap, Cpu, Brain, Sparkles, Key, 
  Trash2, ExternalLink, ShieldCheck, 
  LogOut, Mail, Database, Loader2
} from "lucide-react"

import { 
  Card, CardContent, CardDescription, 
  CardHeader, CardTitle 
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { useToast } from "@/components/ui/use-toast"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"

import { 
  getProviders, saveApiKey, deleteApiKey, 
  type Provider 
} from "@/lib/api"
import { createSupabaseBrowserClient } from "@/lib/supabase-browser"

const LLM_PROVIDERS = [
  {
    id: "claude",
    name: "Anthropic Claude",
    description: "State-of-the-art reasoning and high-context window.",
    link: "https://console.anthropic.com/",
    icon: Sparkles,
  },
  {
    id: "gemini",
    name: "Google Gemini",
    description: "Fast, powerful models with massive context support.",
    link: "https://aistudio.google.com/app/apikey",
    icon: Brain,
  },
]

const EMBEDDING_PROVIDERS = [
  {
    id: "voyage",
    name: "Voyage AI",
    description: "Recommended. Best retrieval performance for RAG.",
    link: "https://dash.voyageai.com/",
    icon: Database,
  },
  {
    id: "openai",
    name: "OpenAI",
    description: "Industry standard embeddings (text-embedding-3).",
    link: "https://platform.openai.com/api-keys",
    icon: Zap,
  },
]

export default function SettingsPage() {
  const router = useRouter()
  const { toast } = useToast()
  const supabase = createSupabaseBrowserClient()
  
  const [loading, setLoading] = useState(true)
  const [providers, setProviders] = useState<Provider[]>([])
  const [userEmail, setUserEmail] = useState<string>("")
  const [savingId, setSavingId] = useState<string | null>(null)
  const [newKeys, setNewKeys] = useState<Record<string, string>>({})

  useEffect(() => {
    async function loadData() {
      try {
        const { data: { user } } = await supabase.auth.getUser()
        if (user?.email) setUserEmail(user.email)
        
        const data = await getProviders()
        setProviders(data)
      } catch (e: any) {
        toast.error("Failed to load settings: " + e.message)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [supabase, toast])

  const handleSaveKey = async (providerId: string) => {
    const key = newKeys[providerId]
    if (!key || key.length < 10) {
      toast.error("Please enter a valid API key")
      return
    }

    setSavingId(providerId)
    try {
      await saveApiKey(providerId, key)
      const updated = await getProviders()
      setProviders(updated)
      setNewKeys(prev => ({ ...prev, [providerId]: "" }))
      toast.success(`${providerId} key saved successfully`)
    } catch (e: any) {
      toast.error("Failed to save key: " + e.message)
    } finally {
      setSavingId(null)
    }
  }

  const handleDeleteKey = async (providerId: string) => {
    if (!confirm(`Are you sure you want to remove the ${providerId} API key?`)) return

    try {
      await deleteApiKey(providerId)
      const updated = await getProviders()
      setProviders(updated)
      toast.success(`${providerId} key removed`)
    } catch (e: any) {
      toast.error("Failed to remove key: " + e.message)
    }
  }

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    router.push("/login")
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  const renderProvider = (p: typeof LLM_PROVIDERS[0]) => {
    const config = providers.find(cp => cp.provider === p.id)
    const Icon = p.icon
    
    return (
      <Card key={p.id} className="overflow-hidden">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Icon className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-base">{p.name}</CardTitle>
              <CardDescription className="text-xs line-clamp-1">{p.description}</CardDescription>
            </div>
          </div>
          {config?.is_active ? (
            <Badge variant="secondary" className="bg-green-50 text-green-700 border-green-200">
              <ShieldCheck className="mr-1 h-3 w-3" /> Connected
            </Badge>
          ) : (
            <Badge variant="outline" className="text-muted-foreground">Not Configured</Badge>
          )}
        </CardHeader>
        <CardContent className="pt-4">
          {config?.is_active ? (
            <div className="flex items-center justify-between gap-4">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-muted-foreground">API Key Preview</span>
                <span className="font-mono text-sm tracking-widest">●●●● {config.key_preview}</span>
              </div>
              <Button 
                variant="outline" 
                size="sm" 
                className="text-red-500 hover:text-red-600 hover:bg-red-50"
                onClick={() => handleDeleteKey(p.id)}
              >
                <Trash2 className="mr-2 h-4 w-4" /> Remove
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <Input 
                  type="password"
                  placeholder="Enter API Key"
                  className="h-9"
                  value={newKeys[p.id] || ""}
                  onChange={(e) => setNewKeys(prev => ({ ...prev, [p.id]: e.target.value }))}
                />
                <Button 
                  size="sm" 
                  disabled={savingId === p.id}
                  onClick={() => handleSaveKey(p.id)}
                >
                  {savingId === p.id ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save"}
                </Button>
              </div>
              <a 
                href={p.link} 
                target="_blank" 
                rel="noreferrer" 
                className="flex items-center text-[10px] text-muted-foreground hover:text-primary"
              >
                Get {p.name} API Key <ExternalLink className="ml-1 h-2 w-2" />
              </a>
            </div>
          )}
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="flex flex-col gap-8 pb-10">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Manage your AI infrastructure and account.</p>
      </div>

      {/* LLM Providers */}
      <section className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold">AI Provider Keys</h2>
          <p className="text-sm text-muted-foreground">Configure which AI models you want to use for generation.</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {LLM_PROVIDERS.map(renderProvider)}
        </div>
      </section>

      <Separator />

      {/* Embedding Providers */}
      <section className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold">Embedding Provider</h2>
          <p className="text-sm text-muted-foreground">Used to convert your knowledge documents into searchable vectors.</p>
        </div>
        <Alert className="bg-sky-50 border-sky-200">
          <Sparkles className="h-4 w-4 text-sky-600" />
          <AlertTitle className="text-sky-800">Pro Tip</AlertTitle>
          <AlertDescription className="text-sky-700 text-xs">
            Voyage AI (voyage-02) provides the best retrieval quality for RAG applications. 
            We recommend it for mission-critical bots.
          </AlertDescription>
        </Alert>
        <div className="grid gap-4 md:grid-cols-2">
          {EMBEDDING_PROVIDERS.map(renderProvider)}
        </div>
      </section>

      <Separator />

      {/* Account Info */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Account Info</h2>
        <Card className="max-w-md">
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                <Mail className="h-6 w-6 text-muted-foreground" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium">Logged in as</p>
                <p className="text-lg">{userEmail}</p>
              </div>
              <Button variant="ghost" className="text-red-500" onClick={handleSignOut}>
                <LogOut className="h-5 w-5" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  )
}
