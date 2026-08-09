export type Tenant = {
  id: string;
  name: string;
  bot_id: string;
  bot_name: string;
  welcome_message: string;
  fallback_message: string;
  primary_color: string;
  system_prompt: string;
  allowed_origins: string[];
  llm_provider: string;
  llm_model: string;
  suggested_questions: string[];
  created_at: string;
};

export type TenantCreate = {
  name: string;
  bot_name?: string;
  welcome_message?: string;
  fallback_message?: string;
  primary_color?: string;
  system_prompt?: string;
  allowed_origins?: string[];
  llm_provider?: string;
  llm_model?: string;
  suggested_questions?: string[];
};

export type Source = {
  id: string;
  tenant_id: string;
  type: string;
  name: string;
  location: string;
  status: string;
  chunk_count: number;
  content_hash: string;
  error_message: string;
  last_indexed: string | null;
  created_at: string;
};

export type SourceStatus = {
  id: string;
  status: string;
  chunk_count: number;
  error_message: string;
};

export type AnalyticsDailyCount = {
  date: string;
  count: number;
};

export type AnalyticsData = {
  total_conversations: number;
  answered_count: number;
  unanswered_count: number;
  answer_rate: number;
  conversations_today: number;
  total_tokens: number;
  top_provider: string;
  top_sources: string[];
  daily_counts: AnalyticsDailyCount[];
  unanswered_questions: string[];
};

export type Conversation = {
  id: string;
  tenant_id: string;
  session_id: string;
  question: string;
  answer: string;
  sources_used: string[];
  was_answered: boolean;
  confidence: string;
  response_type: string;
  created_at: string;
};

export type Lead = {
  id: string;
  tenant_id: string;
  session_id: string;
  name: string;
  email: string;
  created_at: string;
};

export type WidgetConfig = {
  bot_id: string;
  bot_name: string;
  welcome_message: string;
  primary_color: string;
  suggested_questions: string[];
  powered_by: string;
};

export type Provider = {
  provider: string;
  key_preview: string;
  is_active: boolean;
};

export type ModelsDict = {
  claude: string[];
  gemini: string[];
};

import { createSupabaseBrowserClient } from "./supabase-browser"

async function getAuthHeaders(): Promise<HeadersInit> {
  const supabase = createSupabaseBrowserClient()
  const { data: { session } } = await supabase.auth.getSession()
  const token = session?.access_token
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  }
}

const BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

function formatApiErrorBody(data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail?: unknown }).detail
    if (typeof detail === "string") return detail
    if (detail != null) return JSON.stringify(detail)
  }
  try {
    return JSON.stringify(data)
  } catch {
    return "Unknown error"
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  // Public routes do not require authentication
  const isPublic = path.startsWith("/api/widget/") || path.startsWith("/api/chat");
  const authHeaders = isPublic 
    ? { "Content-Type": "application/json" } 
    : await getAuthHeaders();

  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      ...authHeaders,
      ...(init?.headers ?? {}),
    },
  });

  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const data: unknown = await res.json();
      message = formatApiErrorBody(data);
    } catch {
      const text = await res.text().catch(() => "");
      if (text) message = text;
    }
    throw new Error(message);
  }

  // Some endpoints might return an empty body.
  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

async function apiFetchNoBody(path: string, init?: RequestInit): Promise<void> {
  await apiFetch<unknown>(path, init);
}

// Tenants
export async function getTenants(): Promise<Tenant[]> {
  return apiFetch<Tenant[]>("/api/tenants");
}

export async function createTenant(data: TenantCreate): Promise<Tenant> {
  return apiFetch<Tenant>("/api/tenants", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getTenant(id: string): Promise<Tenant> {
  return apiFetch<Tenant>(`/api/tenants/${encodeURIComponent(id)}`);
}

export async function updateTenant(id: string, data: Partial<TenantCreate>): Promise<Tenant> {
  return apiFetch<Tenant>(`/api/tenants/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteTenant(id: string): Promise<void> {
  await apiFetchNoBody(`/api/tenants/${encodeURIComponent(id)}`, { method: "DELETE" });
}

// Sources
export async function getSources(tenantId: string): Promise<Source[]> {
  return apiFetch<Source[]>(`/api/sources/${encodeURIComponent(tenantId)}`);
}

export async function ingestUrl(tenantId: string, url: string, name?: string): Promise<Source> {
  return apiFetch<Source>("/api/sources/ingest/url", {
    method: "POST",
    body: JSON.stringify({
      tenant_id: tenantId,
      url,
      name: name ?? null,
    }),
  });
}

export async function ingestFile(tenantId: string, file: File, name?: string): Promise<Source> {
  const form = new FormData();
  form.append("tenant_id", tenantId);
  if (name) form.append("name", name);
  form.append("file", file);

  const supabase = createSupabaseBrowserClient()
  const { data: { session } } = await supabase.auth.getSession()
  const token = session?.access_token

  const res = await fetch(`${BASE_URL}/api/sources/ingest/file`, {
    method: "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: form,
  });

  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const data: unknown = await res.json();
      message = formatApiErrorBody(data);
    } catch {
      const text = await res.text().catch(() => "");
      if (text) message = text;
    }
    throw new Error(message);
  }

  return (await res.json()) as Source;
}

export async function ingestPdf(tenantId: string, file: File, name?: string): Promise<Source> {
  // Legacy wrapper
  return ingestFile(tenantId, file, name);
}

export async function getSourceStatus(sourceId: string): Promise<SourceStatus> {
  return apiFetch<SourceStatus>(`/api/sources/status/${encodeURIComponent(sourceId)}`);
}

export async function deleteSource(sourceId: string): Promise<void> {
  await apiFetchNoBody(`/api/sources/${encodeURIComponent(sourceId)}`, { method: "DELETE" });
}

export async function reindexSource(sourceId: string): Promise<Source> {
  return apiFetch<Source>(`/api/sources/reindex/${encodeURIComponent(sourceId)}`, {
    method: "POST",
  });
}

// Analytics
export async function getAnalytics(tenantId: string): Promise<AnalyticsData> {
  return apiFetch<AnalyticsData>(`/api/analytics/${encodeURIComponent(tenantId)}`);
}

export async function getConversations(
  tenantId: string,
  limit = 50
): Promise<Conversation[]> {
  const qs = new URLSearchParams({ limit: String(limit) });
  return apiFetch<Conversation[]>(`/api/analytics/${encodeURIComponent(tenantId)}/conversations?${qs}`);
}

export async function getUnanswered(tenantId: string): Promise<Conversation[]> {
  return apiFetch<Conversation[]>(`/api/analytics/${encodeURIComponent(tenantId)}/unanswered`);
}

export async function getLeads(tenantId: string): Promise<Lead[]> {
  return apiFetch<Lead[]>(`/api/analytics/${encodeURIComponent(tenantId)}/leads`);
}

// Widget config
export async function getWidgetConfig(botId: string): Promise<WidgetConfig> {
  return apiFetch<WidgetConfig>(`/api/widget/config/${encodeURIComponent(botId)}`);
}

// Settings / API Keys
export async function getProviders(): Promise<Provider[]> {
  const data = await apiFetch<{ providers: Provider[] }>("/api/settings/providers");
  return data.providers;
}

export async function saveApiKey(provider: string, apiKey: string): Promise<void> {
  await apiFetchNoBody("/api/settings/api-key", {
    method: "POST",
    body: JSON.stringify({ provider, api_key: apiKey }),
  });
}

export async function deleteApiKey(provider: string): Promise<void> {
  await apiFetchNoBody(`/api/settings/api-key/${encodeURIComponent(provider)}`, {
    method: "DELETE",
  });
}

export async function getAvailableModels(): Promise<ModelsDict> {
  return apiFetch<ModelsDict>("/api/settings/models");
}

// Knowledge Graph
export async function getGraphVisualize(botId: string): Promise<{ status: string; image?: string }> {
  return apiFetch<{ status: string; image?: string }>(`/graph/${encodeURIComponent(botId)}/visualize`);
}

export async function rebuildGraph(botId: string): Promise<{ status: string; message: string }> {
  return apiFetch<{ status: string; message: string }>(`/graph/${encodeURIComponent(botId)}/rebuild`, {
    method: "POST",
  });
}

export async function getGraphData(botId: string): Promise<any> {
  return apiFetch<any>(`/graph/${encodeURIComponent(botId)}`);
}

