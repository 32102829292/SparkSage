"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";

interface CostSummary {
  total_cost: number;
  projected_monthly: number;
  total_input_tokens: number;
  total_output_tokens: number;
  by_provider: { name: string; cost: number; input_tokens: number; output_tokens: number }[];
  daily: { date: string; cost: number }[];
}

const fmt = (n: number) => (n < 0.01 ? "<$0.01" : `$${n.toFixed(4)}`);

export default function CostPage() {
  const { data: session, status } = useSession();
  const token = (session as { accessToken?: string })?.accessToken;

  const [stats, setStats] = useState<CostSummary | null>(null);
  const [period, setPeriod] = useState("30d");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    if (status === "loading" || !token) return;
    let isMounted = true;

    const fetchCosts = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(`${API}/api/analytics/costs?period=${period}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error("Failed to fetch cost data");
        const data: CostSummary = await res.json();
        if (isMounted) setStats(data);
      } catch {
        if (isMounted) {
          setError("Unable to load cost data.");
          setStats(null);
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchCosts();
    return () => { isMounted = false; };
  }, [token, period, status]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Cost Tracking</h1>
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="border rounded-lg px-3 py-2 text-sm w-40 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="all">All time</option>
        </select>
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading cost data...</p>
      ) : error ? (
        <Card>
          <CardContent className="py-12 text-center text-red-500">{error}</CardContent>
        </Card>
      ) : stats ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Total Cost", value: fmt(stats.total_cost) },
              { label: "Projected Monthly", value: fmt(stats.projected_monthly) },
              { label: "Input Tokens", value: stats.total_input_tokens.toLocaleString() },
              { label: "Output Tokens", value: stats.total_output_tokens.toLocaleString() },
            ].map(({ label, value }) => (
              <Card key={label}>
                <CardContent className="pt-5">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="text-2xl font-bold">{value}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {stats.daily.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Daily Cost</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={stats.daily}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${Number(v).toFixed(3)}`} />
                    {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                    <Tooltip formatter={(v: any) => [`$${Number(v).toFixed(4)}`, "Cost"]} />
                    <Line
                      type="monotone"
                      dataKey="cost"
                      stroke="#6366f1"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {stats.by_provider.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Cost by Provider</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={stats.by_provider}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${Number(v).toFixed(3)}`} />
                    {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                    <Tooltip formatter={(v: any) => [`$${Number(v).toFixed(4)}`, "Cost"]} />
                    <Bar dataKey="cost" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>

                <div className="mt-4 space-y-2">
                  {stats.by_provider.map((p) => (
                    <div key={p.name} className="flex items-center justify-between text-sm">
                      <span className="font-medium">{p.name}</span>
                      <div className="flex gap-6 text-muted-foreground text-xs">
                        <span>{p.input_tokens.toLocaleString()} in</span>
                        <span>{p.output_tokens.toLocaleString()} out</span>
                        <span className="font-medium text-foreground">{fmt(p.cost)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      ) : (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No cost data yet. Cost tracking applies to paid providers (Anthropic, OpenAI).
          </CardContent>
        </Card>
      )}
    </div>
  );
}