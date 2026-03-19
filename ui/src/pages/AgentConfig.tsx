import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { agents, providers } from "../api/client";

export function AgentConfig() {
  const { name: workspaceName = "", agent: agentName } = useParams<{
    name: string;
    agent?: string;
  }>();
  const isEdit = agentName !== undefined && agentName !== "new";
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [form, setForm] = useState({
    name: "",
    description: "",
    system_prompt: "",
    provider: "",
    model: "",
  });
  const [error, setError] = useState<string | null>(null);

  // Load existing agent in edit mode
  const { data: existingAgent } = useQuery({
    queryKey: ["agent", workspaceName, agentName],
    queryFn: () => agents.get(workspaceName, agentName!),
    enabled: isEdit,
  });

  useEffect(() => {
    if (existingAgent) {
      setForm({
        name: existingAgent.config.name,
        description: existingAgent.config.description,
        system_prompt: existingAgent.config.system_prompt,
        provider: existingAgent.config.provider ?? "",
        model: existingAgent.config.model ?? "",
      });
    }
  }, [existingAgent]);

  const { data: providerList } = useQuery({
    queryKey: ["providers"],
    queryFn: providers.list,
  });

  const { data: modelList } = useQuery({
    queryKey: ["models", form.provider],
    queryFn: () => providers.listModels(form.provider),
    enabled: !!form.provider,
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (isEdit) {
        return agents.update(workspaceName, agentName!, {
          description: form.description,
          system_prompt: form.system_prompt,
          provider: form.provider || null,
          model: form.model || null,
        });
      } else {
        return agents.create(workspaceName, {
          name: form.name,
          description: form.description,
          system_prompt: form.system_prompt,
          provider: form.provider || undefined,
          model: form.model || undefined,
        });
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workspace", workspaceName] });
      navigate(`/workspaces/${workspaceName}/chat`);
    },
    onError: (err: Error) => setError(err.message),
  });

  function set(field: keyof typeof form, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  return (
    <div className="mx-auto max-w-xl p-6">
      <h2 className="mb-6 text-xl font-semibold text-gray-900 dark:text-white">
        {isEdit ? `Edit agent: ${agentName}` : "New agent"}
      </h2>

      <div className="flex flex-col gap-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">
            Name
          </label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
            disabled={isEdit}
            required
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-violet-500 disabled:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">
            Description
          </label>
          <input
            type="text"
            value={form.description}
            onChange={(e) => set("description", e.target.value)}
            required
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-violet-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">
            System prompt
          </label>
          <textarea
            value={form.system_prompt}
            onChange={(e) => set("system_prompt", e.target.value)}
            required
            rows={6}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-violet-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">
              Provider
            </label>
            <select
              value={form.provider}
              onChange={(e) => { set("provider", e.target.value); set("model", ""); }}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-white"
            >
              <option value="">Default</option>
              {providerList?.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">
              Model
            </label>
            <select
              value={form.model}
              onChange={(e) => set("model", e.target.value)}
              disabled={!form.provider}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:opacity-50 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
            >
              <option value="">Default</option>
              {modelList?.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error && <p className="text-xs text-red-500">{error}</p>}

        <div className="flex gap-2">
          <button
            onClick={() => navigate(-1)}
            className="flex-1 rounded-lg border border-gray-300 py-2 text-sm text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300"
          >
            Cancel
          </button>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending || (!form.name && !isEdit) || !form.system_prompt}
            className="flex-1 rounded-lg bg-violet-600 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
          >
            {saveMutation.isPending ? "Saving…" : "Save agent"}
          </button>
        </div>
      </div>
    </div>
  );
}
