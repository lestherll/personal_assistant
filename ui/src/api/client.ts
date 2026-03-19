export class ApiError extends Error {
  status: number;
  constructor(status: number, message?: string) {
    super(message ?? `API error ${status}`);
    this.status = status;
  }
}

export class UnauthorizedError extends ApiError {
  constructor() {
    super(401, "Unauthorized");
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    credentials: "include",
  });
  if (res.status === 401) throw new UnauthorizedError();
  if (!res.ok) {
    let message: string | undefined;
    try {
      const body = await res.json();
      message = body?.detail ?? body?.error;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type?: string;
}

export interface UserResponse {
  id: string;
  username: string;
  email: string;
  created_at: string;
}

export interface RegisterResponse {
  user: UserResponse;
  tokens: TokenResponse;
}

export const auth = {
  login: (username: string, password: string) =>
    apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username, password }).toString(),
    }),

  register: (username: string, email: string, password: string) =>
    apiFetch<RegisterResponse>("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password }),
    }),

  refresh: (refresh_token: string) =>
    apiFetch<TokenResponse>("/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token }),
    }),

  logout: () => apiFetch<void>("/auth/logout", { method: "POST" }),

  listApiKeys: () => apiFetch<ApiKeyResponse[]>("/auth/api-keys"),

  createApiKey: (name: string) =>
    apiFetch<CreateApiKeyResponse>("/auth/api-keys", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),

  revokeApiKey: (id: string) =>
    apiFetch<void>(`/auth/api-keys/${id}`, { method: "DELETE" }),

  rotateApiKey: (id: string) =>
    apiFetch<CreateApiKeyResponse>(`/auth/api-keys/${id}/rotate`, {
      method: "POST",
    }),
};

export interface ApiKeyResponse {
  id: string;
  name: string;
  key_prefix: string;
  is_active: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  created_at: string;
}

export interface CreateApiKeyResponse {
  key: string;
  api_key: ApiKeyResponse;
}

// ---------------------------------------------------------------------------
// Workspaces
// ---------------------------------------------------------------------------

export interface WorkspaceResponse {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceDetailResponse extends WorkspaceResponse {
  agents: AgentResponse[];
}

export interface AgentConfigResponse {
  name: string;
  description: string;
  system_prompt: string;
  provider: string | null;
  model: string | null;
  allowed_tools: string[] | null;
}

export interface AgentResponse {
  config: AgentConfigResponse;
  tools: string[];
  llm_info: Record<string, string | null>;
}

export interface ConversationResponse {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface MessageResponse {
  id: string;
  conversation_id: string;
  role: "human" | "ai" | "system";
  content: string;
  agent_id: string | null;
  created_at: string;
}

export interface WorkspaceChatResponse {
  response: string;
  conversation_id: string;
  agent_used: string;
}

export const workspaces = {
  list: () => apiFetch<WorkspaceResponse[]>("/workspaces/"),

  get: (name: string) => apiFetch<WorkspaceDetailResponse>(`/workspaces/${name}`),

  create: (name: string, description?: string) =>
    apiFetch<WorkspaceResponse>("/workspaces/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description }),
    }),

  update: (name: string, description: string) =>
    apiFetch<WorkspaceResponse>(`/workspaces/${name}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description }),
    }),

  delete: (name: string) =>
    apiFetch<void>(`/workspaces/${name}`, { method: "DELETE" }),

  chat: (
    name: string,
    message: string,
    opts?: {
      conversation_id?: string;
      agent_name?: string;
      provider?: string;
      model?: string;
    },
  ) =>
    apiFetch<WorkspaceChatResponse>(`/workspaces/${name}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, ...opts }),
    }),

  listConversations: (name: string, params?: { skip?: number; limit?: number; q?: string }) => {
    const qs = new URLSearchParams();
    if (params?.skip) qs.set("skip", String(params.skip));
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.q) qs.set("q", params.q);
    const query = qs.toString() ? `?${qs}` : "";
    return apiFetch<ConversationResponse[]>(`/workspaces/${name}/conversations${query}`);
  },

  getMessages: (name: string, conversationId: string) =>
    apiFetch<MessageResponse[]>(
      `/workspaces/${name}/conversations/${conversationId}/messages`,
    ),

  renameConversation: (name: string, conversationId: string, title: string) =>
    apiFetch<void>(`/workspaces/${name}/conversations/${conversationId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    }),
};

// ---------------------------------------------------------------------------
// Agents
// ---------------------------------------------------------------------------

export const agents = {
  list: (workspaceName: string) =>
    apiFetch<AgentResponse[]>(`/workspaces/${workspaceName}/agents/`),

  get: (workspaceName: string, agentName: string) =>
    apiFetch<AgentResponse>(`/workspaces/${workspaceName}/agents/${agentName}`),

  create: (
    workspaceName: string,
    body: {
      name: string;
      description: string;
      system_prompt: string;
      provider?: string;
      model?: string;
      allowed_tools?: string[] | null;
    },
  ) =>
    apiFetch<AgentResponse>(`/workspaces/${workspaceName}/agents/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  update: (
    workspaceName: string,
    agentName: string,
    body: Partial<{
      description: string;
      system_prompt: string;
      provider: string | null;
      model: string | null;
      allowed_tools: string[] | null;
    }>,
  ) =>
    apiFetch<AgentResponse>(`/workspaces/${workspaceName}/agents/${agentName}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  delete: (workspaceName: string, agentName: string) =>
    apiFetch<void>(`/workspaces/${workspaceName}/agents/${agentName}`, {
      method: "DELETE",
    }),
};

// ---------------------------------------------------------------------------
// Providers
// ---------------------------------------------------------------------------

export interface ProviderResponse {
  name: string;
  default_model: string;
}

export const providers = {
  list: () => apiFetch<ProviderResponse[]>("/providers/"),
  listModels: (name: string) =>
    apiFetch<{ name: string; models: string[] }>(`/providers/${name}/models`).then((r) => r.models),
};

// ---------------------------------------------------------------------------
// Usage
// ---------------------------------------------------------------------------

export interface UsageSummaryRecord {
  workspace: string;
  provider: string | null;
  model: string | null;
  period_start: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
}

export interface AgentUsageResponse {
  agent_name: string;
  workspace: string;
  provider: string | null;
  model: string | null;
  period_start: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
}

export const usage = {
  summary: (params?: { start?: string; end?: string }) => {
    const qs = new URLSearchParams();
    if (params?.start) qs.set("start", params.start);
    if (params?.end) qs.set("end", params.end);
    const query = qs.toString() ? `?${qs}` : "";
    return apiFetch<UsageSummaryRecord[]>(`/usage/summary${query}`);
  },
  byAgent: (params?: { start?: string; end?: string }) => {
    const qs = new URLSearchParams();
    if (params?.start) qs.set("start", params.start);
    if (params?.end) qs.set("end", params.end);
    const query = qs.toString() ? `?${qs}` : "";
    return apiFetch<AgentUsageResponse[]>(`/usage/by-agent${query}`);
  },
};

// ---------------------------------------------------------------------------
// Streaming
// ---------------------------------------------------------------------------

export async function streamChat(
  path: string,
  body: Record<string, unknown>,
  onToken: (token: string) => void,
  signal?: AbortSignal,
): Promise<{ conversationId: string; agentUsed: string }> {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (res.status === 401) throw new UnauthorizedError();
  if (!res.ok) throw new ApiError(res.status);

  const conversationId = res.headers.get("X-Conversation-Id") ?? "";
  const agentUsed = res.headers.get("X-Agent-Used") ?? "";

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6);
      if (payload === "[DONE]") return { conversationId, agentUsed };
      if (payload === "[ERROR]") throw new Error("Stream error from server");
      onToken(payload);
    }
  }

  return { conversationId, agentUsed };
}
