"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
  LineChart,
  Line,
} from "recharts";
import { 
  Loader2, 
  Activity, 
  RefreshCw, 
  Zap,
  MessageSquare,
  Clock,
  Hash,
  TrendingUp,
  AlertCircle
} from "lucide-react";

// Theme-aware colors using CSS variables
const COLORS = [
  "hsl(var(--primary))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
  "hsl(var(--destructive))",
  "hsl(var(--chart-7))",
];

interface AnalyticsStats {
  total_messages: number;
  total_responses: number;
  avg_latency_ms: number;
  active_channels: number;
  by_provider: Record<string, number>;
  daily: { date: string; count: number }[];
  hourly?: { hour: string; count: number }[];
  top_channels?: { name: string; count: number }[];
}

export default function AnalyticsPage() {
  const { data: session, status } = useSession();
  const [stats, setStats] = useState<AnalyticsStats | null>(null);
  const [period, setPeriod] = useState("7d");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  
  const token = (session as { accessToken?: string })?.accessToken;

  const fetchAnalytics = useCallback(async (showRefreshingState = false) => {
    if (!token) return null;

    try {
      if (showRefreshingState) {
        setRefreshing(true);
      }

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
      setStats(data);
      setLastUpdated(new Date());
      setError(null);
      return data;
    } catch (err) {
      setError("Unable to load analytics data.");
      setStats(null);
      return null;
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token, period]);

  useEffect(() => {
    if (status === "loading") return;
    if (!token) {
      setLoading(false);
      return;
    }

    fetchAnalytics();
  }, [token, period, status, fetchAnalytics]);

  useEffect(() => {
    if (!autoRefresh || !token) {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      return;
    }

    pollingIntervalRef.current = setInterval(() => {
      fetchAnalytics(true);
    }, 30000);

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [autoRefresh, token, fetchAnalytics]);

  const handleRefresh = useCallback(async () => {
    await fetchAnalytics(true);
  }, [fetchAnalytics]);

  const toggleAutoRefresh = useCallback(() => {
    setAutoRefresh(prev => !prev);
  }, []);

  const providerData = stats?.by_provider
    ? Object.entries(stats.by_provider).map(([name, count]) => ({
        name,
        count,
      }))
    : [];

  const dailyData = stats?.daily ?? [];
  const hourlyData = stats?.hourly ?? [];
  const topChannels = stats?.top_channels ?? [];

  const responseRate = stats?.total_messages 
    ? Math.round((stats.total_responses / stats.total_messages) * 100) 
    : 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (status === "unauthenticated") {
    return (
      <Card className="border-destructive max-w-2xl mx-auto">
        <CardContent className="pt-6">
          <div className="flex items-start space-x-3">
            <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-destructive">Authentication Required</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Please sign in to view analytics.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Analytics</h1>
          <p className="text-sm text-muted-foreground">
            Metrics and insights from your Discord bot
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant={autoRefresh ? "default" : "outline"}
            size="sm"
            onClick={toggleAutoRefresh}
            className="gap-1"
          >
            <Activity className="h-3 w-3" />
            {autoRefresh ? 'Auto (30s)' : 'Manual'}
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            <RefreshCw className={`h-3 w-3 mr-1 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>

          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="bg-background text-foreground border border-input rounded-lg px-3 py-2 text-sm w-32 focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="today">Today</option>
            <option value="7d">7 days</option>
            <option value="30d">30 days</option>
            <option value="all">All time</option>
          </select>
        </div>
      </div>

      {lastUpdated && (
        <p className="text-xs text-muted-foreground">
          Last updated: {lastUpdated.toLocaleTimeString()}
          {autoRefresh && ' (auto-refreshing every 30s)'}
        </p>
      )}

      {error ? (
        <Card className="border-destructive">
          <CardContent className="py-12 text-center">
            <AlertCircle className="h-8 w-8 mx-auto text-destructive mb-2" />
            <p className="text-destructive">{error}</p>
            <Button 
              variant="outline" 
              size="sm" 
              onClick={handleRefresh}
              className="mt-4"
            >
              Try Again
            </Button>
          </CardContent>
        </Card>
      ) : stats ? (
        <>
          {/* Stat Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { 
                label: "Total Messages", 
                value: stats.total_messages,
                icon: MessageSquare,
                color: "text-primary"
              },
              { 
                label: "AI Responses", 
                value: stats.total_responses,
                icon: Zap,
                color: "text-purple-500 dark:text-purple-400"
              },
              { 
                label: "Avg Latency", 
                value: `${stats.avg_latency_ms}ms`,
                icon: Clock,
                color: "text-cyan-500 dark:text-cyan-400"
              },
              { 
                label: "Active Channels", 
                value: stats.active_channels,
                icon: Hash,
                color: "text-emerald-500 dark:text-emerald-400"
              },
            ].map(({ label, value, icon: Icon, color }) => (
              <Card key={label}>
                <CardContent className="pt-5">
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">{label}</p>
                    <Icon className={`h-4 w-4 ${color}`} />
                  </div>
                  <p className="text-2xl font-bold text-foreground mt-1">{value}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Response Rate Card */}
          <div className="grid grid-cols-2 gap-4">
            <Card>
              <CardContent className="pt-5">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-muted-foreground">Response Rate</p>
                  <TrendingUp className="h-4 w-4 text-emerald-500 dark:text-emerald-400" />
                </div>
                <p className="text-2xl font-bold text-foreground mt-1">{responseRate}%</p>
              </CardContent>
            </Card>
          </div>

          {/* Daily Line Chart */}
          {dailyData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm text-foreground font-medium">
                  Messages Per Day
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={dailyData}>
                    <CartesianGrid 
                      strokeDasharray="3 3" 
                      stroke="hsl(var(--border))" 
                    />
                    <XAxis 
                      dataKey="date" 
                      tick={{ 
                        fontSize: 11, 
                        fill: 'hsl(var(--foreground))'
                      }}
                      stroke="hsl(var(--border))"
                    />
                    <YAxis 
                      tick={{ 
                        fontSize: 11, 
                        fill: 'hsl(var(--foreground))'
                      }}
                      stroke="hsl(var(--border))"
                    />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: 'hsl(var(--background))',
                        borderColor: 'hsl(var(--border))',
                        color: 'hsl(var(--foreground))',
                        borderRadius: '0.5rem'
                      }}
                      labelStyle={{ color: 'hsl(var(--foreground))' }}
                      itemStyle={{ color: 'hsl(var(--foreground))' }}
                    />
                    <Line
                      type="monotone"
                      dataKey="count"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* Hourly Data */}
          {hourlyData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm text-foreground font-medium">
                  Hourly Activity
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={hourlyData}>
                    <CartesianGrid 
                      strokeDasharray="3 3" 
                      stroke="hsl(var(--border))" 
                    />
                    <XAxis 
                      dataKey="hour" 
                      tick={{ 
                        fontSize: 11, 
                        fill: 'hsl(var(--foreground))'
                      }}
                      stroke="hsl(var(--border))"
                    />
                    <YAxis 
                      tick={{ 
                        fontSize: 11, 
                        fill: 'hsl(var(--foreground))'
                      }}
                      stroke="hsl(var(--border))"
                    />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: 'hsl(var(--background))',
                        borderColor: 'hsl(var(--border))',
                        color: 'hsl(var(--foreground))',
                        borderRadius: '0.5rem'
                      }}
                      labelStyle={{ color: 'hsl(var(--foreground))' }}
                      itemStyle={{ color: 'hsl(var(--foreground))' }}
                    />
                    <Bar
                      dataKey="count"
                      fill="hsl(var(--chart-2))"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
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
                  <CardTitle className="text-sm text-foreground font-medium">
                    Provider Distribution
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
                        label={({ name, percent = 0, x, y }) => (
                          <text 
                            x={x} 
                            y={y} 
                            fill="hsl(var(--foreground))"
                            fontSize={12}
                            textAnchor="middle"
                            dominantBaseline="middle"
                            className="text-xs font-medium"
                          >
                            {`${name} ${(percent * 100).toFixed(0)}%`}
                          </text>
                        )}
                        labelLine={{ 
                          stroke: 'hsl(var(--muted-foreground))',
                          strokeWidth: 1
                        }}
                      >
                        {providerData.map((_, i) => (
                          <Cell
                            key={i}
                            fill={COLORS[i % COLORS.length]}
                          />
                        ))}
                      </Pie>
                      <Tooltip 
                        contentStyle={{ 
                          backgroundColor: 'hsl(var(--background))',
                          borderColor: 'hsl(var(--border))',
                          color: 'hsl(var(--foreground))',
                          borderRadius: '0.5rem'
                        }}
                        labelStyle={{ color: 'hsl(var(--foreground))' }}
                        itemStyle={{ color: 'hsl(var(--foreground))' }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              {/* Bar Chart */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm text-foreground font-medium">
                    Requests by Provider
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={providerData}>
                      <CartesianGrid 
                        strokeDasharray="3 3" 
                        stroke="hsl(var(--border))" 
                      />
                      <XAxis 
                        dataKey="name" 
                        tick={{ 
                          fontSize: 11, 
                          fill: 'hsl(var(--foreground))'
                        }}
                        stroke="hsl(var(--border))"
                      />
                      <YAxis 
                        tick={{ 
                          fontSize: 11, 
                          fill: 'hsl(var(--foreground))'
                        }}
                        stroke="hsl(var(--border))"
                      />
                      <Tooltip 
                        contentStyle={{ 
                          backgroundColor: 'hsl(var(--background))',
                          borderColor: 'hsl(var(--border))',
                          color: 'hsl(var(--foreground))',
                          borderRadius: '0.5rem'
                        }}
                        labelStyle={{ color: 'hsl(var(--foreground))' }}
                        itemStyle={{ color: 'hsl(var(--foreground))' }}
                      />
                      <Bar
                        dataKey="count"
                        fill="hsl(var(--primary))"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Top Channels */}
          {topChannels.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm text-foreground font-medium">
                  Top Active Channels
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {topChannels.map((channel, i) => (
                    <div key={i} className="flex items-center justify-between">
                      <span className="text-sm text-foreground">#{channel.name}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-foreground">{channel.count}</span>
                        <div 
                          className="h-2 bg-primary rounded-full"
                          style={{ 
                            width: `${(channel.count / Math.max(...topChannels.map(c => c.count))) * 100}px`,
                            maxWidth: '200px'
                          }}
                        />
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
            <Activity className="h-8 w-8 mx-auto mb-2 opacity-50" />
            No analytics data yet. Start using the bot to see stats here.
          </CardContent>
        </Card>
      )}
    </div>
  );
}