import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { usage } from "../api/client";

export function UsageDashboard() {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const params = {
    start: start || undefined,
    end: end || undefined,
  };

  const { data: summaryList } = useQuery({
    queryKey: ["usage-summary", params],
    queryFn: () => usage.summary(params),
  });

  const { data: byAgent } = useQuery({
    queryKey: ["usage-by-agent", params],
    queryFn: () => usage.byAgent(params),
  });

  // Aggregate list of per-workspace/period records into a single display object.
  const summary =
    summaryList && summaryList.length > 0
      ? {
          total_tokens: summaryList.reduce((s, r) => s + r.total_tokens, 0),
          total_prompt_tokens: summaryList.reduce((s, r) => s + r.prompt_tokens, 0),
          total_completion_tokens: summaryList.reduce((s, r) => s + r.completion_tokens, 0),
          request_count: summaryList.length,
          by_day: Object.values(
            summaryList.reduce<
              Record<
                string,
                { date: string; prompt_tokens: number; completion_tokens: number; total_tokens: number }
              >
            >((acc, r) => {
              const date = r.period_start.slice(0, 10);
              if (!acc[date])
                acc[date] = { date, prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 };
              acc[date].prompt_tokens += r.prompt_tokens;
              acc[date].completion_tokens += r.completion_tokens;
              acc[date].total_tokens += r.total_tokens;
              return acc;
            }, {}),
          ).sort((a, b) => a.date.localeCompare(b.date)),
        }
      : null;

  return (
    <div className="mx-auto max-w-4xl p-6">
      <h2 className="mb-6 text-xl font-semibold text-gray-900 dark:text-white">Usage Dashboard</h2>

      {/* Date filters */}
      <div className="mb-6 flex gap-3">
        <div>
          <label className="mb-1 block text-xs text-gray-500">Start</label>
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-gray-500">End</label>
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          />
        </div>
      </div>

      {/* Summary stats */}
      {summary && (
        <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            { label: "Total tokens", value: summary.total_tokens.toLocaleString() },
            { label: "Prompt tokens", value: summary.total_prompt_tokens.toLocaleString() },
            { label: "Completion tokens", value: summary.total_completion_tokens.toLocaleString() },
            { label: "Requests", value: summary.request_count.toLocaleString() },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900"
            >
              <p className="text-xs text-gray-500">{label}</p>
              <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tokens over time */}
      {summary?.by_day && summary.by_day.length > 0 && (
        <div className="mb-8 rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
          <h3 className="mb-4 text-sm font-medium text-gray-700 dark:text-gray-300">
            Tokens over time
          </h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={summary.by_day}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="prompt_tokens" stroke="#8b5cf6" name="Prompt" dot={false} />
              <Line type="monotone" dataKey="completion_tokens" stroke="#06b6d4" name="Completion" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* By agent */}
      {byAgent && byAgent.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
          <h3 className="mb-4 text-sm font-medium text-gray-700 dark:text-gray-300">
            Tokens by agent
          </h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={byAgent}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="agent_name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="prompt_tokens" stackId="a" fill="#8b5cf6" name="Prompt" />
              <Bar dataKey="completion_tokens" stackId="a" fill="#06b6d4" name="Completion" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {summaryList === undefined && (
        <p className="text-sm text-gray-400">Loading usage data…</p>
      )}

      {summaryList !== undefined && summaryList.length === 0 && (
        <div className="rounded-xl border border-dashed border-gray-300 p-8 text-center dark:border-gray-700">
          <p className="font-medium text-gray-700 dark:text-gray-300">No usage data yet</p>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Start a conversation with one of your agents to see token usage and cost analytics here.
          </p>
        </div>
      )}
    </div>
  );
}
