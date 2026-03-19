import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { auth, type ApiKeyResponse } from "../api/client";

function KeyRow({ k, onRevoke }: { k: ApiKeyResponse; onRevoke: () => void }) {
  return (
    <li className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
      <div>
        <p className="font-medium text-gray-800 dark:text-gray-200">{k.name}</p>
        <p className="mt-0.5 text-xs text-gray-500">
          Prefix: <code className="font-mono">{k.key_prefix}</code>
          {k.last_used_at && (
            <> · Last used {new Date(k.last_used_at).toLocaleDateString()}</>
          )}
          {!k.is_active && <span className="ml-2 text-red-400">revoked</span>}
        </p>
      </div>
      {k.is_active && (
        <button
          onClick={() => {
            if (confirm(`Revoke key "${k.name}"?`)) onRevoke();
          }}
          className="rounded px-2 py-1 text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
        >
          Revoke
        </button>
      )}
    </li>
  );
}

export function ApiKeys() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [rawKey, setRawKey] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  const { data: keys } = useQuery({
    queryKey: ["api-keys"],
    queryFn: auth.listApiKeys,
  });

  const createMutation = useMutation({
    mutationFn: () => auth.createApiKey(name),
    onSuccess: (resp) => {
      qc.invalidateQueries({ queryKey: ["api-keys"] });
      setRawKey(resp.key);
      setName("");
      setConfirmed(false);
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => auth.revokeApiKey(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h2 className="mb-6 text-xl font-semibold text-gray-900 dark:text-white">API Keys</h2>

      {/* Key revealed modal */}
      {rawKey && !confirmed && (
        <div className="mb-6 rounded-xl border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-900/20">
          <p className="mb-2 text-sm font-medium text-green-800 dark:text-green-300">
            Your new API key (shown once — copy it now!)
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded bg-green-100 px-3 py-2 font-mono text-sm text-green-900 dark:bg-green-900/40 dark:text-green-200 break-all">
              {rawKey}
            </code>
            <button
              onClick={() => navigator.clipboard.writeText(rawKey)}
              className="rounded bg-green-600 px-3 py-2 text-xs text-white hover:bg-green-700"
            >
              Copy
            </button>
          </div>
          <button
            onClick={() => { setConfirmed(true); setRawKey(null); }}
            className="mt-3 text-xs text-green-600 underline hover:text-green-700 dark:text-green-400"
          >
            I've copied this key
          </button>
        </div>
      )}

      <ul className="mb-8 space-y-2">
        {keys?.map((k) => (
          <KeyRow key={k.id} k={k} onRevoke={() => revokeMutation.mutate(k.id)} />
        ))}
        {keys?.length === 0 && (
          <li className="rounded-xl border border-dashed border-gray-300 p-6 text-center dark:border-gray-700">
            <p className="font-medium text-gray-700 dark:text-gray-300">No API keys yet</p>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              API keys let you access your assistant programmatically — from scripts, tools, or other apps.
            </p>
          </li>
        )}
      </ul>

      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-900">
        <h3 className="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">
          Create new key
        </h3>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Key name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-violet-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          />
          <button
            onClick={() => createMutation.mutate()}
            disabled={!name.trim() || createMutation.isPending}
            className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
          >
            {createMutation.isPending ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
