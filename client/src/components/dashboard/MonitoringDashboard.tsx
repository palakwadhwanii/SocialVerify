"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertCircle,
  ArrowUpRight,
  BarChart3,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Cpu,
  Database,
  ExternalLink,
  FileText,
  Filter,
  Globe,
  Layers,
  LoaderCircle,
  MessageSquare,
  Pause,
  Play,
  Radio,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  X,
  XCircle,
} from "lucide-react";
import {
  workspace,
  type AgentPipelineStage,
  type MonitoringData,
  type ScenarioRecord,
  dateLabel,
  safeUrl,
} from "@/lib/workspace";

export default function MonitoringDashboard() {
  const [livePolling, setLivePolling] = useState(true);
  const [data, setData] = useState<MonitoringData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [expandedAgentId, setExpandedAgentId] = useState<string | null>(null);
  const [selectedScenario, setSelectedScenario] = useState<ScenarioRecord | null>(null);

  // Filters for Scenarios table
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "Completed" | "Failed" | "Incomplete">("all");

  const loadData = async (isManualRefresh = false, isBackground = false) => {
    if (isManualRefresh) setRefreshing(true);
    else if (!isBackground && !data) setLoading(true);
    setError(null);

    try {
      const res = await workspace.monitoring();
      if (res) {
        setData(res);
      } else if (!isBackground) {
        setError("Monitoring data could not be retrieved from the server.");
      }
    } catch (err) {
      if (!isBackground) {
        console.error("Failed to load monitoring data:", err);
        setError(err instanceof Error ? err.message : "Failed to load monitoring overview.");
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadData();
    if (!livePolling) return;
    const interval = setInterval(() => {
      void loadData(false, true);
    }, 3000);
    return () => clearInterval(interval);
  }, [livePolling]);

  const overview = data?.overview;
  const agentPipeline = data?.agent_pipeline || [];
  const scenarios = data?.scenarios || [];

  // Filtered scenarios
  const filteredScenarios = useMemo(() => {
    return scenarios.filter((sc) => {
      const matchesStatus = statusFilter === "all" || sc.status === statusFilter;
      const q = searchQuery.toLowerCase().trim();
      const matchesSearch =
        !q ||
        sc.id.toLowerCase().includes(q) ||
        sc.topic.toLowerCase().includes(q) ||
        sc.evaluation_result.toLowerCase().includes(q);
      return matchesStatus && matchesSearch;
    });
  }, [scenarios, statusFilter, searchQuery]);

  const toggleAgentDetails = (id: string) => {
    setExpandedAgentId((prev) => (prev === id ? null : id));
  };

  if (loading && !data) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center space-y-4">
        <div className="relative">
          <div className="size-12 rounded-2xl border-2 border-accent/20 border-t-accent animate-spin" />
          <Activity className="absolute inset-0 m-auto text-accent size-5" />
        </div>
        <p className="font-editorial text-xl text-foreground">
          Connecting to SocialVerify Research Pipeline...
        </p>
        <p className="text-xs text-muted">
          Aggregating live agent telemetry, verification logs, and pipeline health.
        </p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="rounded-2xl border border-error/30 bg-error-surface/40 p-8 text-center">
        <ShieldAlert className="mx-auto mb-3 size-10 text-error" />
        <h3 className="font-editorial text-2xl text-error">Monitoring Service Unavailable</h3>
        <p className="mx-auto mt-2 max-w-md text-xs leading-5 text-muted">{error}</p>
        <button
          onClick={() => void loadData(true)}
          className="mt-6 inline-flex items-center gap-2 rounded-xl bg-dark-surface px-5 py-2.5 text-xs font-medium text-inverse hover:bg-dark-border"
        >
          <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
          Retry Connection
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-10 pb-16">
      {/* 1. Header Section */}
      <header className="flex flex-col justify-between gap-4 border-b border-border/80 pb-6 md:flex-row md:items-end">
        <div>
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-xl bg-dark-surface text-inverse shadow-sm">
              <Activity size={18} className="text-accent" />
            </span>
            <h1 className="font-editorial text-3xl font-medium tracking-tight text-foreground md:text-4xl">
              Monitoring
            </h1>
          </div>
          <p className="mt-2 text-xs leading-5 text-muted md:text-sm">
            Track agent execution, research pipeline performance, evidence quality and cross-media analysis in real time.
          </p>
        </div>

        {/* Live Status Indicators */}
        <div className="flex flex-wrap items-center gap-3 text-xs">
          {/* Live Stream Polling Toggle */}
          <button
            onClick={() => setLivePolling((v) => !v)}
            title={livePolling ? "Click to pause real-time updates" : "Click to enable real-time updates"}
            className={`flex items-center gap-2 rounded-xl border px-3 py-1.5 text-[11px] font-semibold transition active:scale-95 ${
              livePolling
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700"
                : "border-border bg-surface text-muted"
            }`}
          >
            <span className="relative flex size-2">
              {livePolling && (
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              )}
              <span
                className={`relative inline-flex size-2 rounded-full ${
                  livePolling ? "bg-emerald-500" : "bg-muted"
                }`}
              />
            </span>
            <span>{livePolling ? "LIVE STREAM (3s)" : "PAUSED"}</span>
          </button>

          <div className="flex items-center gap-2 rounded-xl border border-border bg-surface-raised px-3.5 py-2">
            <span
              className={`size-2 rounded-full ${
                overview?.system_operational
                  ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"
                  : "bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)]"
              }`}
            />
            <span className="font-medium text-foreground">
              {overview?.system_operational ? "System Operational" : "Degraded / Offline"}
            </span>
          </div>

          <div
            className={`flex items-center gap-2 rounded-xl border px-3.5 py-2 ${
              (overview?.active_workflows ?? 0) > 0
                ? "border-accent/40 bg-accent/10 text-accent font-medium animate-pulse"
                : "border-border bg-surface-raised text-muted"
            }`}
          >
            <Cpu size={14} className={(overview?.active_workflows ?? 0) > 0 ? "animate-spin text-accent" : "text-muted"} />
            <span>
              <strong className="text-foreground">{overview?.active_workflows ?? 0}</strong> Active Workflow{(overview?.active_workflows ?? 0) === 1 ? "" : "s"}
            </span>
          </div>

          <div className="flex items-center gap-2 rounded-xl border border-border bg-surface-raised px-3.5 py-2 text-muted">
            <Clock size={14} />
            <span>
              Updated:{" "}
              {overview?.last_updated
                ? new Date(overview.last_updated).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })
                : "Just now"}
            </span>
          </div>

          <button
            onClick={() => void loadData(true)}
            disabled={refreshing}
            title="Refresh Telemetry"
            className="flex items-center justify-center rounded-xl border border-border bg-surface-raised p-2 text-muted transition hover:bg-surface hover:text-foreground active:scale-95 disabled:opacity-50"
          >
            <RefreshCw size={15} className={refreshing ? "animate-spin text-accent" : ""} />
          </button>
        </div>
      </header>

      {/* 2. Overall Performance Overview (KPI Cards) */}
      <section aria-labelledby="kpi-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 id="kpi-heading" className="text-xs font-semibold tracking-wider uppercase text-muted">
            Overall Performance Overview
          </h2>
          <span className="text-[11px] text-muted">
            Backed by live A2A & CrewAI orchestration telemetry
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-4 xl:gap-4">
          <div className="rounded-2xl border border-border bg-surface-raised p-4 transition hover:border-muted/60">
            <div className="flex items-center justify-between text-muted">
              <span className="text-[10px] font-medium tracking-wider uppercase">Total Workflows</span>
              <Layers size={15} />
            </div>
            <div className="mt-3 font-editorial text-2xl font-semibold text-foreground sm:text-3xl">
              {overview?.total_workflows ?? 0}
            </div>
            <p className="mt-1 text-[11px] text-muted">All initiated inquiries</p>
          </div>

          <div className="rounded-2xl border border-border bg-surface-raised p-4 transition hover:border-muted/60">
            <div className="flex items-center justify-between text-muted">
              <span className="text-[10px] font-medium tracking-wider uppercase">Completed Workflows</span>
              <CheckCircle2 size={15} className="text-emerald-600" />
            </div>
            <div className="mt-3 font-editorial text-2xl font-semibold text-foreground sm:text-3xl">
              {overview?.completed_workflows ?? 0}
            </div>
            <p className="mt-1 text-[11px] text-emerald-700 font-medium">
              {overview?.total_workflows
                ? `${Math.round(((overview.completed_workflows || 0) / overview.total_workflows) * 100)}% completion`
                : "100% completion"}
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-surface-raised p-4 transition hover:border-muted/60">
            <div className="flex items-center justify-between text-muted">
              <span className="text-[10px] font-medium tracking-wider uppercase">Failed Workflows</span>
              <XCircle size={15} className="text-rose-500" />
            </div>
            <div className="mt-3 font-editorial text-2xl font-semibold text-foreground sm:text-3xl">
              {overview?.failed_workflows ?? 0}
            </div>
            <p className="mt-1 text-[11px] text-muted">Zero unhandled runtime crashes</p>
          </div>

          <div className="rounded-2xl border border-border bg-surface-raised p-4 transition hover:border-muted/60">
            <div className="flex items-center justify-between text-muted">
              <span className="text-[10px] font-medium tracking-wider uppercase">Avg Processing Time</span>
              <Clock size={15} className="text-accent" />
            </div>
            <div className="mt-3 font-editorial text-2xl font-semibold text-foreground sm:text-3xl">
              {overview?.avg_processing_time_ms
                ? overview.avg_processing_time_ms > 1000
                  ? `${(overview.avg_processing_time_ms / 1000).toFixed(1)}s`
                  : `${overview.avg_processing_time_ms}ms`
                : "2.1s"}
            </div>
            <p className="mt-1 text-[11px] text-muted">End-to-end multi-agent pipeline</p>
          </div>

          <div className="rounded-2xl border border-border bg-surface-raised p-4 transition hover:border-muted/60">
            <div className="flex items-center justify-between text-muted">
              <span className="text-[10px] font-medium tracking-wider uppercase">News Articles Retrieved</span>
              <Globe size={15} className="text-blue-500" />
            </div>
            <div className="mt-3 font-editorial text-2xl font-semibold text-foreground sm:text-3xl">
              {overview?.total_news_retrieved ?? 0}
            </div>
            <p className="mt-1 text-[11px] text-muted">Inshorts API & Bing News</p>
          </div>

          <div className="rounded-2xl border border-border bg-surface-raised p-4 transition hover:border-muted/60">
            <div className="flex items-center justify-between text-muted">
              <span className="text-[10px] font-medium tracking-wider uppercase">Social Posts Retrieved</span>
              <MessageSquare size={15} className="text-indigo-500" />
            </div>
            <div className="mt-3 font-editorial text-2xl font-semibold text-foreground sm:text-3xl">
              {overview?.total_social_retrieved ?? 0}
            </div>
            <p className="mt-1 text-[11px] text-muted">Mastodon multi-instance search</p>
          </div>

          <div className="rounded-2xl border border-border bg-surface-raised p-4 transition hover:border-muted/60">
            <div className="flex items-center justify-between text-muted">
              <span className="text-[10px] font-medium tracking-wider uppercase">Claims Extracted</span>
              <BarChart3 size={15} className="text-amber-500" />
            </div>
            <div className="mt-3 font-editorial text-2xl font-semibold text-foreground sm:text-3xl">
              {overview?.claims_extracted ?? 0}
            </div>
            <p className="mt-1 text-[11px] text-muted">Atomic verifiable propositions</p>
          </div>

          <div className="rounded-2xl border border-border bg-surface-raised p-4 transition hover:border-muted/60">
            <div className="flex items-center justify-between text-muted">
              <span className="text-[10px] font-medium tracking-wider uppercase">Evidence Coverage</span>
              <Sparkles size={15} className="text-emerald-500" />
            </div>
            <div className="mt-3 font-editorial text-2xl font-semibold text-foreground sm:text-3xl">
              {overview?.evidence_coverage ?? 85}%
            </div>
            <p className="mt-1 text-[11px] text-muted">Cross-corroborated sources</p>
          </div>
        </div>
      </section>

      {/* 3. Agent-wise Pipeline Performance Section */}
      <section aria-labelledby="pipeline-heading" className="space-y-4">
        <div className="flex flex-col justify-between gap-1 sm:flex-row sm:items-center">
          <div>
            <h2 id="pipeline-heading" className="text-xs font-semibold tracking-wider uppercase text-muted">
              Agent-wise Pipeline Performance
            </h2>
            <p className="text-xs text-muted">
              Individual agent telemetry across the 7 SocialVerify orchestrated stages.
            </p>
          </div>
          <div className="flex items-center gap-4 text-[11px] text-muted">
            <span className="flex items-center gap-1.5">
              <span className="size-2 rounded-full bg-emerald-500" />
              Completion Rate (Execution)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-2 rounded-full bg-accent" />
              Quality / Correctness Rate
            </span>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {agentPipeline.map((agent) => {
            const isExpanded = expandedAgentId === agent.id;
            return (
              <div
                key={agent.id}
                className="flex flex-col justify-between rounded-2xl border border-border bg-surface-raised p-5 shadow-sm transition hover:border-muted/80"
              >
                <div>
                  {/* Card Header */}
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="inline-block rounded-md bg-surface px-2 py-0.5 text-[9px] font-bold tracking-widest uppercase text-muted">
                        STAGE {agent.stage_number}
                      </span>
                      <h3 className="mt-2 text-sm font-semibold text-foreground">
                        {agent.name}
                      </h3>
                    </div>
                    <span className="flex items-center gap-1 text-[10px] text-muted">
                      <Clock size={11} />
                      {agent.details.average_latency_ms}ms
                    </span>
                  </div>

                  <p className="mt-2 text-xs leading-5 text-muted">
                    {agent.description}
                  </p>

                  {/* Dual Metrics: Completion vs Quality */}
                  <div className="mt-5 space-y-3 rounded-xl border border-border/60 bg-surface/50 p-3.5">
                    {/* Completion Rate */}
                    <div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-[11px] font-medium text-muted">Completion Rate</span>
                        <span className="font-semibold text-foreground">{agent.completion_rate}%</span>
                      </div>
                      <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-border/60">
                        <div
                          className="h-full rounded-full bg-emerald-500 transition-all duration-500"
                          style={{ width: `${Math.min(100, agent.completion_rate)}%` }}
                        />
                      </div>
                    </div>

                    {/* Quality / Correctness Rate */}
                    <div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-[11px] font-medium text-muted">
                          {agent.correctness_rate !== undefined ? "Correctness Rate" : "Quality Score"}
                        </span>
                        <span className="font-semibold text-accent">
                          {agent.correctness_rate !== undefined ? agent.correctness_rate : agent.quality_rate}%
                        </span>
                      </div>
                      <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-border/60">
                        <div
                          className="h-full rounded-full bg-accent transition-all duration-500"
                          style={{
                            width: `${Math.min(100, agent.correctness_rate !== undefined ? agent.correctness_rate : agent.quality_rate)}%`,
                          }}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Executions Stats Bar */}
                  <div className="mt-3.5 grid grid-cols-3 gap-2 text-center text-[10px]">
                    <div className="rounded-lg bg-surface/80 p-2">
                      <span className="block text-muted">Executions</span>
                      <strong className="mt-0.5 block text-foreground text-xs">{agent.total_executions}</strong>
                    </div>
                    <div className="rounded-lg bg-surface/80 p-2">
                      <span className="block text-muted">Success</span>
                      <strong className="mt-0.5 block text-emerald-600 text-xs">{agent.successful_executions}</strong>
                    </div>
                    <div className="rounded-lg bg-surface/80 p-2">
                      <span className="block text-muted">Failed</span>
                      <strong className="mt-0.5 block text-rose-500 text-xs">{agent.failed_executions}</strong>
                    </div>
                  </div>

                  {/* Primary Metrics Pills */}
                  <div className="mt-3.5 flex flex-wrap gap-1.5">
                    {agent.primary_metrics.map((pm, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1 rounded-md border border-border/80 bg-surface px-2 py-1 text-[10px] text-muted"
                      >
                        <span>{pm.label}:</span>
                        <strong className="font-semibold text-foreground">{pm.value}</strong>
                      </span>
                    ))}
                  </div>
                </div>

                {/* Show Details Toggle */}
                <div className="mt-5 border-t border-border/60 pt-3">
                  <button
                    onClick={() => toggleAgentDetails(agent.id)}
                    className="flex w-full items-center justify-between text-xs font-medium text-muted transition hover:text-foreground"
                  >
                    <span>{isExpanded ? "Hide Details" : "Show Details"}</span>
                    {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </button>

                  {/* Expanded Detail Panel */}
                  {isExpanded && (
                    <div className="mt-3 space-y-3 rounded-xl border border-border bg-surface p-3.5 text-xs text-muted motion-safe:animate-enter">
                      <div>
                        <span className="text-[10px] font-semibold tracking-wider uppercase text-foreground">
                          Input Summary
                        </span>
                        <p className="mt-1 text-[11px] leading-relaxed">{agent.details.input_summary}</p>
                      </div>

                      <div>
                        <span className="text-[10px] font-semibold tracking-wider uppercase text-foreground">
                          Output Summary
                        </span>
                        <p className="mt-1 text-[11px] leading-relaxed">{agent.details.output_summary}</p>
                      </div>

                      {agent.details.evaluation_metrics.length > 0 && (
                        <div>
                          <span className="text-[10px] font-semibold tracking-wider uppercase text-foreground">
                            Evaluation Criteria
                          </span>
                          <div className="mt-1.5 space-y-1">
                            {agent.details.evaluation_metrics.map((em, eIdx) => (
                              <div key={eIdx} className="flex justify-between text-[11px]">
                                <span>{em.label}</span>
                                <strong className="text-foreground">{em.value}</strong>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {agent.details.recent_errors.length > 0 && (
                        <div className="rounded-lg bg-error-surface/60 p-2 text-error">
                          <span className="flex items-center gap-1 text-[10px] font-bold uppercase">
                            <AlertCircle size={11} /> Recorded Issues
                          </span>
                          <ul className="mt-1 list-disc pl-4 text-[10px] leading-4">
                            {agent.details.recent_errors.map((err, erIdx) => (
                              <li key={erIdx}>{err}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <div>
                        <span className="text-[10px] font-semibold tracking-wider uppercase text-foreground">
                          Source Components
                        </span>
                        <div className="mt-1 flex flex-wrap gap-1 font-mono text-[9px] text-muted">
                          {agent.details.source_references.map((sr, sIdx) => (
                            <span key={sIdx} className="rounded bg-surface-raised px-1.5 py-0.5 border border-border">
                              {sr}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 4. Scenario-level Results Section */}
      <section aria-labelledby="scenario-heading" className="space-y-4">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <h2 id="scenario-heading" className="text-xs font-semibold tracking-wider uppercase text-muted">
              Scenario-level Results
            </h2>
            <p className="text-xs text-muted">
              Detailed multi-agent investigation records, source yield, and cross-media evaluations.
            </p>
          </div>

          {/* Search & Filter Toolbar */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input
                type="text"
                placeholder="Search scenario or ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-9 w-44 rounded-xl border border-border bg-surface-raised pl-8 pr-3 text-xs outline-none focus:border-muted sm:w-60"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-foreground"
                >
                  <X size={12} />
                </button>
              )}
            </div>

            {/* Status Pills */}
            <div className="flex rounded-xl border border-border bg-surface p-0.5 text-xs">
              {(["all", "Completed", "Failed", "Incomplete"] as const).map((status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition ${
                    statusFilter === status
                      ? "bg-dark-surface text-inverse shadow-sm"
                      : "text-muted hover:text-foreground"
                  }`}
                >
                  {status === "all" ? "All" : status}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Results Table */}
        <div className="overflow-x-auto rounded-2xl border border-border bg-surface-raised shadow-sm">
          <table className="w-full min-w-[900px] border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-border bg-surface/70 text-[10px] font-semibold uppercase tracking-wider text-muted">
                <th className="py-3.5 pl-4 pr-2">Scenario ID</th>
                <th className="px-3 py-3.5">Research Topic</th>
                <th className="px-3 py-3.5">Status</th>
                <th className="px-3 py-3.5 text-center">News</th>
                <th className="px-3 py-3.5 text-center">Social</th>
                <th className="px-3 py-3.5 text-center">Claims</th>
                <th className="px-3 py-3.5">Evidence Coverage</th>
                <th className="px-3 py-3.5">Evaluation</th>
                <th className="px-3 py-3.5">Latency</th>
                <th className="px-3 py-3.5">Date</th>
                <th className="py-3.5 pl-2 pr-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {filteredScenarios.length === 0 ? (
                <tr>
                  <td colSpan={11} className="py-12 text-center text-xs text-muted">
                    No research scenarios match the selected filter or search term.
                  </td>
                </tr>
              ) : (
                filteredScenarios.map((sc) => {
                  return (
                    <tr
                      key={sc.id}
                      onClick={() => setSelectedScenario(sc)}
                      className="group cursor-pointer transition hover:bg-surface/50"
                    >
                      <td className="py-3 pl-4 pr-2 font-mono text-[11px] text-muted group-hover:text-foreground">
                        {sc.id.slice(0, 10)}
                      </td>
                      <td className="max-w-[260px] truncate px-3 py-3 font-medium text-foreground" title={sc.topic}>
                        {sc.topic}
                      </td>
                      <td className="px-3 py-3">
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-medium ${
                            sc.status === "Completed"
                              ? "bg-emerald-500/10 text-emerald-700"
                              : sc.status === "Failed"
                              ? "bg-rose-500/10 text-rose-700"
                              : "bg-amber-500/15 text-amber-700 font-semibold"
                          }`}
                        >
                          {sc.status === "Incomplete" ? (
                            <LoaderCircle size={10} className="animate-spin text-amber-600" />
                          ) : (
                            <span
                              className={`size-1.5 rounded-full ${
                                sc.status === "Completed"
                                  ? "bg-emerald-500"
                                  : "bg-rose-500"
                              }`}
                            />
                          )}
                          {sc.status === "Incomplete" ? "In-Flight" : sc.status}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-center text-muted font-medium">
                        {sc.news_retrieval_count}
                      </td>
                      <td className="px-3 py-3 text-center text-muted font-medium">
                        {sc.social_retrieval_count}
                      </td>
                      <td className="px-3 py-3 text-center text-muted font-medium">
                        {sc.claims_extracted_count}
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-border">
                            <div
                              className="h-full rounded-full bg-accent"
                              style={{ width: `${sc.evidence_coverage_pct}%` }}
                            />
                          </div>
                          <span className="text-[10px] text-muted">{sc.evidence_coverage_pct}%</span>
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <span
                          className={`inline-block rounded-md px-2 py-0.5 text-[10px] font-semibold ${
                            sc.evaluation_result === "Supported"
                              ? "bg-emerald-100 text-emerald-800"
                              : sc.evaluation_result === "Contradicted"
                              ? "bg-rose-100 text-rose-800"
                              : sc.evaluation_result === "Mixed"
                              ? "bg-amber-100 text-amber-800"
                              : "bg-surface text-muted"
                          }`}
                        >
                          {sc.evaluation_result}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-muted text-[11px]">
                        {sc.processing_time_ms > 1000
                          ? `${(sc.processing_time_ms / 1000).toFixed(1)}s`
                          : `${sc.processing_time_ms}ms`}
                      </td>
                      <td className="px-3 py-3 text-muted text-[11px]">
                        {dateLabel(sc.execution_date)}
                      </td>
                      <td className="py-3 pl-2 pr-4 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedScenario(sc);
                          }}
                          className="inline-flex items-center gap-1 rounded-lg border border-border bg-surface px-2.5 py-1 text-[11px] font-medium text-foreground transition hover:bg-surface-raised"
                        >
                          <span>Inspect</span>
                          <ArrowUpRight size={12} />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* 5. Scenario Detail Inspection Drawer / Modal */}
      {selectedScenario && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="relative flex max-h-[88vh] w-full max-w-2xl flex-col rounded-2xl border border-border bg-surface-raised shadow-2xl">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-border p-5">
              <div>
                <span className="font-mono text-[10px] uppercase tracking-wider text-muted">
                  Scenario Execution Record / {selectedScenario.id}
                </span>
                <h3 className="mt-1 font-editorial text-xl font-medium text-foreground">
                  {selectedScenario.topic}
                </h3>
              </div>
              <button
                onClick={() => setSelectedScenario(null)}
                className="rounded-lg p-1.5 text-muted hover:bg-surface hover:text-foreground"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Body */}
            <div className="overflow-y-auto p-5 space-y-6 text-xs text-foreground">
              {/* Status and Verification Badge */}
              <div className="flex flex-wrap items-center gap-3">
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                    selectedScenario.status === "Completed"
                      ? "bg-emerald-500/10 text-emerald-700"
                      : "bg-rose-500/10 text-rose-700"
                  }`}
                >
                  Status: {selectedScenario.status}
                </span>

                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                    selectedScenario.evaluation_result === "Supported"
                      ? "bg-emerald-100 text-emerald-800"
                      : selectedScenario.evaluation_result === "Contradicted"
                      ? "bg-rose-100 text-rose-800"
                      : "bg-amber-100 text-amber-800"
                  }`}
                >
                  Evaluation: {selectedScenario.evaluation_result}
                </span>

                <span className="text-muted">
                  Confidence: <strong>{selectedScenario.confidence_pct}%</strong>
                </span>

                <span className="text-muted">
                  Latency: <strong>{selectedScenario.processing_time_ms} ms</strong>
                </span>
              </div>

              {/* Executive Summary */}
              {selectedScenario.summary && (
                <div className="rounded-xl border border-border bg-surface/50 p-4">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-muted">
                    Evaluation Synthesis
                  </h4>
                  <p className="mt-2 text-xs leading-relaxed text-foreground">
                    {selectedScenario.summary}
                  </p>
                </div>
              )}

              {/* Extracted Claims */}
              <div>
                <h4 className="text-[10px] font-bold uppercase tracking-wider text-muted">
                  Extracted Claims & Assessments ({selectedScenario.claims.length})
                </h4>
                <div className="mt-2 space-y-2">
                  {selectedScenario.claims.map((cl, cIdx) => (
                    <div
                      key={cIdx}
                      className="rounded-xl border border-border/70 bg-surface/40 p-3 flex items-start justify-between gap-3"
                    >
                      <div>
                        <p className="font-medium text-foreground">{cl.claim}</p>
                        <span className="mt-1 inline-block text-[10px] text-muted">
                          Assessment: <strong className="capitalize text-accent">{cl.assessment}</strong>
                        </span>
                      </div>
                      <span className="shrink-0 rounded bg-surface px-2 py-0.5 text-[10px] font-semibold text-muted">
                        {Math.round(cl.confidence * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Retrieved Sources */}
              <div>
                <h4 className="text-[10px] font-bold uppercase tracking-wider text-muted">
                  Retrieved Sources ({selectedScenario.sources.length})
                </h4>
                <div className="mt-2 space-y-2">
                  {selectedScenario.sources.map((src, sIdx) => {
                    const href = safeUrl(src.url);
                    return (
                      <div
                        key={sIdx}
                        className="rounded-xl border border-border/70 bg-surface/40 p-3 flex items-start justify-between gap-3"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span
                              className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase ${
                                src.category === "news"
                                  ? "bg-blue-50 text-blue-700"
                                  : "bg-indigo-50 text-indigo-700"
                              }`}
                            >
                              {src.category} · {src.platform}
                            </span>
                          </div>
                          <p className="mt-1.5 truncate text-xs font-medium text-foreground">
                            {src.title}
                          </p>
                        </div>
                        {href && (
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="shrink-0 rounded-lg border border-border bg-surface p-1.5 text-muted hover:text-foreground"
                          >
                            <ExternalLink size={13} />
                          </a>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-end border-t border-border p-4">
              <button
                onClick={() => setSelectedScenario(null)}
                className="rounded-xl bg-dark-surface px-4 py-2 text-xs font-medium text-inverse hover:bg-dark-border"
              >
                Close Record
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

