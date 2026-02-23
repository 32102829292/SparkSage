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
  PieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
} from "recharts";

const COLORS = ["#6366f1", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b"];

interface AnalyticsStats {
  total_messages: number;
  total_responses: number;
  avg_latency_ms: number;
  active_channels: number;
  by_provider: Record<string, number>;
  daily: { date: string; count: number }[];
}

export default function AnalyticsPage() {
  const { data: session, status } = useSession();

  const [stats, setStats] = useState<AnalyticsStats | null>(null);
  const [period, setPeriod] = useState("7d");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const token = (session as { accessToken?: string })?.accessToken;

  useEffect(() => {
    if (status === "loading") return;

    if (!token) {
      setLoading(false);
      return;
    }

    let isMounted = true;

    const fetchAnalytics = async () => {
      try {
        setLoading(true);
        setError(null);

        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/analytics/summary?period=${period}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (!res.ok) {
          throw new Error("Failed to fetch analytics");
        }

        const data: AnalyticsStats = await res.json();

        if (isMounted) {
          setStats(data);
        }
      } catch (err) {
        if (isMounted) {
          setError("Unable to load analytics data.");
          setStats(null);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchAnalytics();

    return () => {
      isMounted = false;
    };
  }, [token, period, status]);

  const providerData =
    stats?.by_provider
      ? Object.entries(stats.by_provider).map(([name, count]) => ({
          name,
          count,
        }))
      : [];

  const dailyData = stats?.daily ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Analytics</h1>

        {/* ✅ Plain Select (No shadcn error) */}
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="border rounded-lg px-3 py-2 text-sm w-40 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="today">Today</option>
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="all">All time</option>
        </select>
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading analytics...</p>
      ) : error ? (
        <Card>
          <CardContent className="py-12 text-center text-red-500">
            {error}
          </CardContent>
        </Card>
      ) : stats ? (
        <>
          {/* Stat Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Total Messages", value: stats.total_messages },
              { label: "AI Responses", value: stats.total_responses },
              { label: "Avg Latency", value: `${stats.avg_latency_ms}ms` },
              { label: "Active Channels", value: stats.active_channels },
            ].map(({ label, value }) => (
              <Card key={label}>
                <CardContent className="pt-5">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="text-2xl font-bold">{value}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Daily Line Chart */}
          {dailyData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">
                  Messages Per Day
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={dailyData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="count"
                      stroke="#6366f1"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* Provider Charts */}
          {providerData.length > 0 && (
            <div className="grid md:grid-cols-2 gap-4">
              {/* Pie Chart */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">
                    Provider Usage
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie
                        data={providerData}
                        dataKey="count"
                        nameKey="name"
                        outerRadius={80}
                        label
                      >
                        {providerData.map((_, i) => (
                          <Cell
                            key={i}
                            fill={COLORS[i % COLORS.length]}
                          />
                        ))}
                      </Pie>
                      <Legend />
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              {/* Bar Chart */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">
                    Requests by Provider
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={providerData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Bar
                        dataKey="count"
                        fill="#6366f1"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </div>
          )}
        </>
      ) : (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No analytics data yet. Start using the bot to see stats here.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
