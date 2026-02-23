"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Activity, Cpu, Wifi, WifiOff, Server, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import type { ProviderItem, ProvidersResponse } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface BotStatus {
  online: boolean;
  username: string;
  latency_ms: number;
  guild_count: number;
  guilds: { id: string; name: string; member_count: number }[];
}

export default function DashboardOverview() {
  const { data: session, status } = useSession();

  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [providersData, setProvidersData] = useState<ProvidersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const token = (session as { accessToken?: string })?.accessToken;

  useEffect(() => {
    if (status === "loading") return;
    if (!token) {
      setLoading(false);
      return;
    }

    const fetchData = async () => {
      setLoading(true);
      setError(null);

      const results = await Promise.allSettled([
        api.getBotStatus(token),
        api.getProviders(token),
      ]);

      const botResult = results[0] as PromiseSettledResult<BotStatus>;
      const provResult = results[1] as PromiseSettledResult<ProvidersResponse>;

      if (botResult.status === "fulfilled") {
        setBotStatus(botResult.value);
      }

      if (provResult.status === "fulfilled") {
        setProvidersData(provResult.value);
      }

      if (
        botResult.status === "rejected" &&
        provResult.status === "rejected"
      ) {
        setError("Failed to load dashboard data.");
      }

      setLoading(false);
    };

    fetchData();
  }, [token, status]);

  const primaryProvider = providersData?.providers.find(
    (p: ProviderItem) => p.is_primary
  );

  if (loading) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Loading dashboard...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-red-500 text-sm">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold">Overview</h1>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">

        {/* Bot Status */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Bot Status</CardTitle>
            {botStatus?.online ? (
              <Wifi className="h-4 w-4 text-green-600" />
            ) : (
              <WifiOff className="h-4 w-4 text-muted-foreground" />
            )}
          </CardHeader>
          <CardContent>
            <Badge variant={botStatus?.online ? "default" : "secondary"}>
              {botStatus?.online ? "Online" : "Offline"}
            </Badge>
          </CardContent>
        </Card>

        {/* Latency */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Latency</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {botStatus?.latency_ms != null
                ? `${Math.round(botStatus.latency_ms)}ms`
                : "--"}
            </p>
          </CardContent>
        </Card>

        {/* Servers */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Servers</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {botStatus?.guild_count ?? "--"}
            </p>
          </CardContent>
        </Card>

        {/* Active Provider */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Active Provider
            </CardTitle>
            <Cpu className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {primaryProvider ? (
              <>
                <p className="text-lg font-semibold">
                  {primaryProvider.display_name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {primaryProvider.model}
                </p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">--</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Connected Servers */}
      {botStatus?.guilds?.length ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Connected Servers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {botStatus.guilds.map((guild) => (
                <div
                  key={guild.id}
                  className="flex items-center justify-between rounded-lg border px-3 py-2"
                >
                  <span className="text-sm font-medium">
                    {guild.name}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {guild.member_count} members
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* Fallback Chain */}
      {providersData?.fallback_order?.length ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Fallback Chain
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center gap-2">
              {providersData.fallback_order.map((name, i) => {
                const prov = providersData.providers.find(
                  (p) => p.name === name
                );

                return (
                  <div key={name} className="flex items-center gap-2">
                    <div className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5">
                      <div
                        className={`h-2 w-2 rounded-full ${
                          prov?.configured
                            ? "bg-green-500"
                            : "bg-gray-300"
                        }`}
                      />
                      <span className="text-sm">
                        {prov?.display_name || name}
                      </span>
                      {prov?.is_primary && (
                        <Badge
                          variant="secondary"
                          className="ml-1 text-xs"
                        >
                          Primary
                        </Badge>
                      )}
                    </div>
                    {i < providersData.fallback_order.length - 1 && (
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
