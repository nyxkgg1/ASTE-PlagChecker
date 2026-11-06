
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  Award,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  Eye,
  FileText,
  FolderOpen,
  RefreshCw,
  ScanSearch,
  ShieldCheck,
  Users,
  ClipboardCheck,
  CalendarDays,
  Database,
  ArrowUpRight,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { apiGet } from "../api/client.ts";
import type { CertificateRow, ReferenceDocument } from "../api/types";
import FilePreviewModal from "../components/FilePreviewModal";
import OrganizationMap from "../components/OrganizationMap";

type Point = {
  name: string;
  value: number;
};

type DashboardData = {
  generated_at?: string;
  summary: {
    total_documents: number;
    total_users: number;
    average_plagiarism_score: number | null;
    average_ai_score: number | null;
    pending_analyses: number | null;
    completed_scans: number | null;
    failed_scans: number | null;
    pending_reference_requests: number | null;
  };
  date_wise_scans: { date: string; count: number }[];
  similarity_trend: { date: string; average_score: number }[];
  ai_score_trend: { date: string; average_score: number }[];
  department_submissions: Point[];
  department_similarity_scores: Point[];
  department_ai_scores: Point[];
  document_status_distribution: Point[];
  user_role_distribution: Point[];
  organization_locations: {
    id: string;
    name: string;
    latitude: number;
    longitude: number;
    documents_scanned: number;
  }[];
  recent_scans: {
    id: string;
    title: string;
    file_name?: string;
    mime_type?: string;
    department: string | null;
    status: string;
    plagiarism_score: number | null;
    ai_score: number | null;
    ai_confidence?: number | null;
    ai_status?: string | null;
    created_at: string | null;
  }[];
};

type PreviewEntry = {
  title: string;
  fileName: string;
  endpoint: string;
  detail: string;
};

const emptyData: DashboardData = {
  summary: {
    total_documents: 0,
    total_users: 0,
    average_plagiarism_score: null,
    average_ai_score: null,
    pending_analyses: null,
    completed_scans: null,
    failed_scans: null,
    pending_reference_requests: null,
  },
  date_wise_scans: [],
  similarity_trend: [],
  ai_score_trend: [],
  department_submissions: [],
  department_similarity_scores: [],
  department_ai_scores: [],
  document_status_distribution: [],
  user_role_distribution: [],
  organization_locations: [],
  recent_scans: [],
};

const fmt = (value: number | null | undefined) =>
  value == null ? "—" : value.toLocaleString("en-IN");

const pct = (value: number | null | undefined) =>
  value == null ? "—" : `${value.toFixed(1)}%`;

const dateLabel = (value: string) => {
  const d = new Date(`${value}T00:00:00`);
  return Number.isNaN(d.getTime())
    ? value
    : d.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
      });
};

const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid #d8e5ee",
  boxShadow: "0 8px 24px rgba(24, 67, 99, 0.12)",
};

function Panel({
  title,
  subtitle,
  children,
  action,
  className = "",
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`min-w-0 rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm md:p-6 ${className}`}
    >
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-Arial bold tracking-tight text-slate-900">
            {title}
          </h2>
          <p className="mt-1.5 text-xs leading-5 text-slate-500">
            {subtitle}
          </p>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function KpiCard({
  title,
  value,
  description,
  icon: Icon,
  accent,
  loading,
}: {
  title: string;
  value: string;
  description: string;
  icon: React.ElementType;
  accent: string;
  loading: boolean;
}) {
  return (
    <article className="group relative overflow-hidden rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md">
      <div
        className={`absolute inset-x-0 top-0 h-1 ${accent.split(" ")[0]}`}
      />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-Arial semibold text-slate-500">{title}</p>
          <p className="mt-3 text-3xl font-Arial bold tracking-tight text-slate-900">
            {loading ? (
              <span className="inline-block h-9 w-16 animate-pulse rounded-lg bg-slate-100" />
            ) : (
              value
            )}
          </p>
        </div>
        <div className={`rounded-xl p-3 ${accent.split(" ").slice(1).join(" ")}`}>
          <Icon size={20} strokeWidth={1.9} />
        </div>
      </div>
      <p className="mt-4 text-xs leading-5 text-slate-500">{description}</p>
    </article>
  );
}

function EmptyState({
  title = "No data for this period",
  description = "Data will appear here when it becomes available.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div className="flex min-h-60 flex-col items-center justify-center px-4 py-8 text-center">
      <div className="mb-3 rounded-2xl bg-slate-50 p-3">
        <Activity size={22} className="text-slate-400" />
      </div>
      <p className="text-sm font-Arial semibold text-slate-700">{title}</p>
      <p className="mt-1.5 max-w-xs text-xs leading-5 text-slate-500">
        {description}
      </p>
    </div>
  );
}

function DonutPanel({
  title,
  subtitle,
  data,
}: {
  title: string;
  subtitle: string;
  data: Point[];
}) {
  const colors = [
    "#2f75b5",
    "#55a6d8",
    "#e9a23b",
    "#20598f",
    "#83c5df",
    "#61798a",
  ];

  return (
    <Panel title={title} subtitle={subtitle}>
      {data.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius={65}
                outerRadius={96}
                paddingAngle={3}
                stroke="white"
                strokeWidth={3}
              >
                {data.map((item, index) => (
                  <Cell
                    key={item.name}
                    fill={colors[index % colors.length]}
                  />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend
                verticalAlign="bottom"
                iconType="circle"
                iconSize={8}
                wrapperStyle={{ fontSize: 11, paddingTop: 12 }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}

function StatusBadge({ status }: { status: string }) {
  const normalized = status.toUpperCase();

  const style =
    normalized === "COMPLETED" || normalized === "APPROVED"
      ? "bg-emerald-50 text-emerald-700 ring-emerald-600/15"
      : normalized === "FAILED" || normalized === "REJECTED"
        ? "bg-rose-50 text-rose-700 ring-rose-600/15"
        : normalized === "PROCESSING"
          ? "bg-blue-50 text-blue-700 ring-blue-600/15"
          : "bg-amber-50 text-amber-700 ring-amber-600/15";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-Arial bold tracking-wide ring-1 ring-inset ${style}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {normalized.replace(/_/g, " ")}
    </span>
  );
}

function RecentFilesPanel({
  title,
  subtitle,
  icon: Icon,
  items,
  loading,
  action,
  onPreview,
}: {
  title: string;
  subtitle: string;
  icon: React.ElementType;
  items: PreviewEntry[];
  loading: boolean;
  action: React.ReactNode;
  onPreview: (item: PreviewEntry) => void;
}) {
  return (
    <Panel title={title} subtitle={subtitle} action={action}>
      <div className="space-y-2">
        {loading &&
          Array.from({ length: 3 }, (_, index) => (
            <div className="recent-file-skeleton" key={index}>
              <span />
              <div><i /><i /></div>
              <span />
            </div>
          ))}
        {!loading &&
          items.map((item) => (
            <button
              type="button"
              key={item.endpoint}
              className="recent-file-row"
              onClick={() => onPreview(item)}
              aria-label={`Preview ${item.title}`}
            >
              <span className="recent-file-icon"><Icon size={17} /></span>
              <span className="recent-file-copy">
                <strong title={item.title}>{item.title}</strong>
                <small title={item.detail}>{item.detail}</small>
              </span>
              <span className="recent-file-view">
                <Eye size={15} />
                <span>Preview</span>
              </span>
            </button>
          ))}
        {!loading && items.length === 0 && (
          <div className="recent-file-empty">
            <FolderOpen size={19} />
            <span>Nothing here yet</span>
          </div>
        )}
      </div>
    </Panel>
  );
}

export default function AdminDashboard() {
  const [data, setData] = useState<DashboardData>(emptyData);
  const [certificates, setCertificates] = useState<CertificateRow[]>([]);
  const [referenceDocuments, setReferenceDocuments] = useState<ReferenceDocument[]>([]);
  const [days, setDays] = useState("30");
  const [loading, setLoading] = useState(true);
  const [previewListsLoading, setPreviewListsLoading] = useState(true);
  const [error, setError] = useState("");
  const [previewListsError, setPreviewListsError] = useState("");
  const [activePreview, setActivePreview] = useState<PreviewEntry | null>(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setPreviewListsLoading(true);
    setError("");
    setPreviewListsError("");

    const [dashboardResult, certificatesResult, referencesResult] =
      await Promise.allSettled([
        apiGet<Partial<DashboardData>>(`/admin/dashboard?days=${days}`),
        apiGet<CertificateRow[]>("/admin/certificates"),
        apiGet<ReferenceDocument[]>("/reference"),
      ]);

    if (dashboardResult.status === "fulfilled") {
      const result = dashboardResult.value;
      setData({
        ...emptyData,
        ...result,
        summary: {
          ...emptyData.summary,
          ...(result.summary ?? {}),
        },
      });
    } else {
      setError(
        dashboardResult.reason instanceof Error
          ? dashboardResult.reason.message
          : "Could not load dashboard data.",
      );
    }

    const previewErrors: string[] = [];
    if (certificatesResult.status === "fulfilled") {
      setCertificates(certificatesResult.value);
    } else {
      setCertificates([]);
      previewErrors.push("Generated certificates could not be loaded.");
    }
    if (referencesResult.status === "fulfilled") {
      setReferenceDocuments(referencesResult.value);
    } else {
      setReferenceDocuments([]);
      previewErrors.push("Reference documents could not be loaded.");
    }
    setPreviewListsError(previewErrors.join(" "));
    setLoading(false);
    setPreviewListsLoading(false);
  }, [days]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const s = data.summary;
  const scannedPreviews = data.recent_scans.slice(0, 4).map((scan) => ({
    title: scan.title,
    fileName: scan.file_name ?? scan.title,
    endpoint: `/scans/${encodeURIComponent(scan.id)}/document`,
    detail: scan.created_at
      ? `Scanned ${new Date(scan.created_at).toLocaleDateString("en-IN")}`
      : "Scanned document",
  }));
  const certificatePreviews = certificates.slice(0, 4).map((certificate) => ({
    title: certificate.document_title || certificate.certificate_number,
    fileName: `${certificate.certificate_number}.pdf`,
    endpoint: `/admin/certificates/${encodeURIComponent(certificate.id)}/download`,
    detail: `Certificate ${certificate.certificate_number}`,
  }));
  const referencePreviews = referenceDocuments.slice(0, 4).map((reference) => ({
    title: reference.title,
    fileName: reference.file_name ?? reference.title,
    endpoint: `/reference/${encodeURIComponent(reference.id)}/document`,
    detail: `${reference.document_type ?? "Reference"} · Version ${reference.current_version ?? 1}`,
  }));

  return (
    <div className="min-h-screen bg-[#f5f7fb] text-slate-900">
      {/* Top navigation */}
      <header className="admin-dashboard-header border-b border-slate-200/80 bg-white/95 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-4 px-5 py-4 md:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#10284a] text-white shadow-sm">
              <ShieldCheck size={23} strokeWidth={1.8} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-Arial extrabold tracking-tight text-[#10284a]">
                  ASTE <span className="text-blue-600">Insight</span>
                </h1>
                <span className="hidden rounded-md bg-blue-50 px-2 py-0.5 text-[9px] font-Arial bold uppercase tracking-wider text-blue-700 sm:inline-flex">
                  Admin
                </span>
              </div>
              <p className="mt-0.5 text-[11px] text-slate-500">
                Aircraft and system testing establishment
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <div className="hidden items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 sm:flex">
              <CalendarDays size={15} className="text-slate-400" />
              Reporting period
            </div>
            <select
              aria-label="Dashboard reporting period"
              value={days}
              onChange={(event) => setDays(event.target.value)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-Arial semibold text-slate-700 outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-500/10"
            >
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
              <option value="365">Last 12 months</option>
            </select>
            <button
              onClick={() => void loadDashboard()}
              disabled={loading}
              aria-label="Refresh dashboard"
              title="Refresh dashboard"
              className="rounded-xl border border-slate-200 bg-white p-2.5 text-slate-600 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw
                size={17}
                className={loading ? "animate-spin" : ""}
              />
            </button>
          </div>
        </div>
      </header>

      <main className="admin-dashboard-main mx-auto max-w-[1600px] space-y-6 px-5 py-7 md:px-8 md:py-9">
        <section className="dashboard-quick-overview">
          <div className="dashboard-quick-heading">
            <div>
              <span className="dashboard-quick-kicker">ASTE INSIGHT</span>
              <h2>Dashboard overview</h2>
              <p>Choose a workspace to continue.</p>
            </div>
            {data.generated_at && (
              <span className="dashboard-quick-updated">
                Updated {new Date(data.generated_at).toLocaleTimeString("en-IN", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            )}
          </div>

          <div className="dashboard-quick-metrics">
            {[
              {
                title: "Documents",
                value: fmt(s.total_documents),
                to: "/documents",
                icon: FileText,
                detail: "Browse scanned documents",
                tone: "blue",
              },
              {
                title: "Users",
                value: fmt(s.total_users),
                to: "/admin/users",
                icon: Users,
                detail: "Manage system accounts",
                tone: "violet",
              },
              {
                title: "Pending requests",
                value: fmt(s.pending_reference_requests),
                to: "/admin/database",
                icon: ClipboardCheck,
                detail: "Review reference requests",
                tone: "amber",
              },
              {
                title: "Failed scans",
                value: fmt(s.failed_scans),
                to: "/admin/audit-logs",
                icon: AlertTriangle,
                detail: "Inspect scan activity",
                tone: "rose",
              },
            ].map(({ title, value, to, icon: Icon, detail, tone }) => (
              <Link
                className={`dashboard-quick-card dashboard-quick-card-${tone}`}
                key={title}
                to={to}
              >
                <span className="dashboard-quick-icon">
                  <Icon size={19} aria-hidden="true" />
                </span>
                <span className="dashboard-quick-copy">
                  <span>{title}</span>
                  <strong>{loading ? "—" : value}</strong>
                  <small>{detail}</small>
                </span>
                <ArrowUpRight
                  className="dashboard-quick-arrow"
                  size={17}
                  aria-hidden="true"
                />
              </Link>
            ))}
          </div>

          <nav className="dashboard-shortcuts" aria-label="Quick links">
            <Link to="/scan"><ScanSearch size={16} />Start a scan</Link>
            <Link to="/admin/certificates"><Award size={16} />Certificates</Link>
            <Link to="/admin/database"><Database size={16} />Manage references</Link>
          </nav>
          {error && (
            <div className="dashboard-quick-error" role="alert">
              <AlertTriangle size={16} />
              <span>Dashboard metrics could not be loaded: {error}</span>
              <button type="button" onClick={() => void loadDashboard()}>Retry</button>
            </div>
          )}
        </section>

        <details className="dashboard-details">
          <summary>
            <span>
              <strong>Detailed reports</strong>
              <small>Charts, recent activity, and document previews</small>
            </span>
            <span className="dashboard-details-toggle" aria-hidden="true" />
          </summary>
          <div className="dashboard-details-content">
        {/* Welcome banner */}
        <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#0d1d36] via-[#12345b] to-[#175c91] px-6 py-8 text-white shadow-lg shadow-blue-950/10 md:px-9 md:py-10">
          <div className="pointer-events-none absolute -right-16 -top-28 h-80 w-80 rounded-full border border-white/10" />
          <div className="pointer-events-none absolute -right-2 -top-16 h-64 w-64 rounded-full border border-white/10" />
          <div className="pointer-events-none absolute -bottom-32 right-36 h-64 w-64 rounded-full bg-sky-400/10 blur-3xl" />

          <div className="relative flex flex-wrap items-end justify-between gap-6">
            <div className="max-w-2xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-sky-300/20 bg-sky-200/10 px-3 py-1.5 text-[10px] font-Arial bold uppercase tracking-[0.18em] text-sky-200">
                <Activity size={13} />
                Intelligence & analytics
              </div>
              <h2 className="mt-5 text-2xl font-Arial bold tracking-tight md:text-3xl">
                Operational overview
              </h2>
              <p className="mt-3 max-w-xl text-sm leading-6 text-blue-100/80">
                Monitor document submissions, plagiarism analysis, processing
                activity and user operations from one central dashboard.
              </p>
            </div>

            <div className="min-w-44 rounded-2xl border border-white/15 bg-white/[0.07] p-4 backdrop-blur-sm">
              <p className="text-[10px] font-Arial bold uppercase tracking-[0.16em] text-blue-200">
                Selected period
              </p>
              <p className="mt-2 text-2xl font-Arial bold">
                {days === "365" ? "12 months" : `${days} days`}
              </p>
              <p className="mt-1 text-[11px] text-blue-100/70">
                {loading ? "Updating statistics…" : "Dashboard reporting window"}
              </p>
            </div>
          </div>

          <div className="relative mt-7 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-white/10 pt-4 text-[11px] text-blue-100/70">
            <span className="inline-flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              Secured reporting workspace
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Database size={13} />
              Live application data
            </span>
            {data.generated_at && (
              <span className="sm:ml-auto">
                Last updated{" "}
                {new Date(data.generated_at).toLocaleString("en-IN")}
              </span>
            )}
          </div>
        </section>

        {error && (
          <div className="flex items-start gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
            <AlertTriangle size={19} className="mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="font-Arial semibold">Dashboard data could not be loaded</p>
              <p className="mt-1 text-xs leading-5">{error}</p>
            </div>
            <button
              onClick={() => void loadDashboard()}
              className="rounded-lg bg-white px-3 py-2 text-xs font-Arial bold text-rose-700 ring-1 ring-rose-200 hover:bg-rose-100"
            >
              Retry
            </button>
          </div>
        )}

        {/* Main metrics */}
        <section>
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-base font-Arial bold tracking-tight text-slate-900">
                Key performance indicators
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                At-a-glance metrics for your reporting period
              </p>
            </div>
            <span className="text-[10px] font-Arial semibold uppercase tracking-wider text-slate-400">
              Overview
            </span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              title="Total documents"
              value={fmt(s.total_documents)}
              description="Documents recorded in the selected period"
              icon={FileText}
              accent="bg-blue-500 bg-blue-50 text-blue-700"
              loading={loading}
            />
            <KpiCard
              title="Registered users"
              value={fmt(s.total_users)}
              description="Accounts registered in the system"
              icon={Users}
              accent="bg-violet-500 bg-violet-50 text-violet-700"
              loading={loading}
            />
            <KpiCard
              title="Average similarity"
              value={pct(s.average_plagiarism_score)}
              description="Mean detected text similarity"
              icon={ScanSearch}
              accent="bg-amber-500 bg-amber-50 text-amber-700"
              loading={loading}
            />
            <KpiCard
              title="Average AI-writing estimate"
              value={pct(s.average_ai_score)}
              description="Average completed classifier estimate; not proof of authorship"
              icon={BrainCircuit}
              accent="bg-teal-500 bg-teal-50 text-teal-700"
              loading={loading}
            />
          </div>
        </section>

        {/* Processing metrics */}
        <section>
          <div className="mb-4">
            <h2 className="text-base font-Arial bold tracking-tight text-slate-900">
              Processing & approvals
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Current workload and scan outcomes within the selected period
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              title="Pending analyses"
              value={fmt(s.pending_analyses)}
              description="Analyses awaiting completion"
              icon={Clock3}
              accent="bg-orange-500 bg-orange-50 text-orange-700"
              loading={loading}
            />
            <KpiCard
              title="Completed scans"
              value={fmt(s.completed_scans)}
              description="Successfully processed documents"
              icon={CheckCircle2}
              accent="bg-emerald-500 bg-emerald-50 text-emerald-700"
              loading={loading}
            />
            <KpiCard
              title="Failed scans"
              value={fmt(s.failed_scans)}
              description="Scans that may require investigation"
              icon={AlertTriangle}
              accent="bg-rose-500 bg-rose-50 text-rose-700"
              loading={loading}
            />
            <KpiCard
              title="Pending requests"
              value={fmt(s.pending_reference_requests)}
              description="Reference-document requests awaiting review"
              icon={ClipboardCheck}
              accent="bg-indigo-500 bg-indigo-50 text-indigo-700"
              loading={loading}
            />
          </div>
        </section>

        <section>
          <div className="mb-4">
            <h2 className="text-base font-Arial bold tracking-tight text-slate-900">
              Your document library
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Open a secure preview of recent scans, certificates, and reference files.
            </p>
            {previewListsError && (
              <p className="mt-2 text-xs text-rose-700" role="status">
                {previewListsError}
              </p>
            )}
          </div>
          <div className="grid gap-5 xl:grid-cols-3">
            <RecentFilesPanel
              title="Recently scanned"
              subtitle="Documents submitted for analysis"
              icon={FileText}
              items={scannedPreviews}
              loading={loading || previewListsLoading}
              onPreview={setActivePreview}
              action={
                <Link className="recent-files-link" to="/documents">All documents</Link>
              }
            />
            <RecentFilesPanel
              title="Generated certificates"
              subtitle="Recently issued analysis certificates"
              icon={Award}
              items={certificatePreviews}
              loading={previewListsLoading}
              onPreview={setActivePreview}
              action={
                <Link className="recent-files-link" to="/admin/certificates">All certificates</Link>
              }
            />
            <RecentFilesPanel
              title="Reference documents"
              subtitle="Files used as comparison references"
              icon={FolderOpen}
              items={referencePreviews}
              loading={previewListsLoading}
              onPreview={setActivePreview}
              action={
                <Link className="recent-files-link" to="/admin/database">Manage references</Link>
              }
            />
          </div>
        </section>

        {/* Charts */}
        <section>
          <div className="mb-4">
            <h2 className="text-base font-Arial bold tracking-tight text-slate-900">
              Document analytics
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Submission activity and detected similarity over time
            </p>
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <Panel
              title="Scanning activity"
              subtitle="Number of documents recorded per day"
              action={
                <span className="rounded-lg bg-blue-50 px-2.5 py-1.5 text-[10px] font-Arial bold text-blue-700">
                  DAILY VOLUME
                </span>
              }
            >
              {data.date_wise_scans.length === 0 ? (
                <EmptyState />
              ) : (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={data.date_wise_scans}
                      margin={{ top: 8, right: 8, left: -20, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient
                          id="scanFill"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop offset="0%" stopColor="#2f75b5" stopOpacity={0.22} />
                          <stop offset="95%" stopColor="#2f75b5" stopOpacity={0.01} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid
                        stroke="#edf1f7"
                        strokeDasharray="3 3"
                        vertical={false}
                      />
                      <XAxis
                        dataKey="date"
                        tickFormatter={dateLabel}
                        tick={{ fontSize: 10, fill: "#61798a" }}
                        axisLine={false}
                        tickLine={false}
                        dy={8}
                      />
                      <YAxis
                        allowDecimals={false}
                        tick={{ fontSize: 10, fill: "#61798a" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        contentStyle={tooltipStyle}
                        labelFormatter={(label) => dateLabel(String(label))}
                      />
                      <Area
                        type="monotone"
                        dataKey="count"
                        name="Documents"
                        stroke="#2f75b5"
                        strokeWidth={2.5}
                        fill="url(#scanFill)"
                        activeDot={{ r: 5, strokeWidth: 0 }}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Panel>

            <Panel
              title="Similarity trend"
              subtitle="Average plagiarism similarity over time"
              action={
                <span className="rounded-lg bg-violet-50 px-2.5 py-1.5 text-[10px] font- bold text-violet-700">
                  SCORE %
                </span>
              }
            >
              {data.similarity_trend.length === 0 ? (
                <EmptyState />
              ) : (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                      data={data.similarity_trend}
                      margin={{ top: 8, right: 8, left: -10, bottom: 0 }}
                    >
                      
                      <CartesianGrid
                        stroke="#edf1f7"
                        strokeDasharray="3 3"
                        vertical={false}
                      />
                      
                      <XAxis
                        dataKey="date"
                        tickFormatter={dateLabel}
                        tick={{ fontSize: 10, fill: "#61798a" }}
                        axisLine={false}
                        tickLine={false}
                        dy={8}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tickFormatter={(value) => `${value}%`}
                        tick={{ fontSize: 10, fill: "#61798a" }}
                        axisLine={false}
                        tickLine={false}
                        width={42}
                      />
                      <Tooltip
                        contentStyle={tooltipStyle}
                        labelFormatter={(label) => dateLabel(String(label))}
                        formatter={(value) => [
                          `${Number(value).toFixed(1)}%`,
                          "Similarity",
                        ]}
                      />
                      <Line
                        type="monotone"
                        dataKey="average_score"
                        name="Similarity"
                        stroke="#e9a23b"
                        strokeWidth={2.5}
                        dot={{ r: 3, fill: "#e9a23b", strokeWidth: 0 }}
                        activeDot={{ r: 6, strokeWidth: 0 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Panel>
          </div>
        </section>

        {/* Distribution charts */}
        <section>
          <div className="mb-4">
            <h2 className="text-base font-Arial bold tracking-tight text-slate-900">
              System distribution
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Scan processing outcomes and account roles
            </p>
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <DonutPanel
              title="Document status"
              subtitle="Documents grouped by processing status"
              data={data.document_status_distribution}
            />
            <DonutPanel
              title="User roles"
              subtitle="Active accounts grouped by assigned role"
              data={data.user_role_distribution}
            />
          </div>
        </section>

        {/* Additional analytics, only when backed by data */}
        {(data.department_submissions.length > 0 ||
          data.department_similarity_scores.length > 0 ||
          data.department_ai_scores.length > 0 ||
          data.ai_score_trend.length > 0) && (
          <section>
            <div className="mb-4">
              <h2 className="text-base font-Arial bold tracking-tight text-slate-900">
                Advanced analytics
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                Additional metrics where source data is available
              </p>
            </div>

            <div className="grid gap-5 xl:grid-cols-2">
              {data.department_submissions.length > 0 && (
                <Panel
                  title="Department submissions"
                  subtitle="Documents submitted by department"
                >
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={data.department_submissions}
                        layout="vertical"
                        margin={{ left: 12, right: 18 }}
                      >
                        <CartesianGrid
                          stroke="#edf1f7"
                          strokeDasharray="3 3"
                          horizontal={false}
                        />
                        <XAxis type="number" allowDecimals={false} />
                        <YAxis
                          type="category"
                          dataKey="name"
                          width={100}
                          tick={{ fontSize: 11, fill: "#64748b" }}
                        />
                        <Tooltip contentStyle={tooltipStyle} />
                        <Bar
                          dataKey="value"
                          name="Documents"
                          fill="#2f75b5"
                          radius={[0, 6, 6, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </Panel>
              )}

              {data.department_similarity_scores.length > 0 && (
                <Panel
                  title="Department similarity comparison"
                  subtitle="Average similarity score by department"
                >
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={data.department_similarity_scores}>
                        <CartesianGrid
                          stroke="#edf1f7"
                          strokeDasharray="3 3"
                          vertical={false}
                        />
                        <XAxis
                          dataKey="name"
                          tick={{ fontSize: 10, fill: "#64748b" }}
                        />
                        <YAxis domain={[0, 100]} />
                        <Tooltip
                          contentStyle={tooltipStyle}
                          formatter={(value) => [
                            `${Number(value).toFixed(1)}%`,
                            "Similarity",
                          ]}
                        />
                        <Bar
                          dataKey="value"
                          name="Similarity"
                          fill="#e9a23b"
                          radius={[6, 6, 0, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </Panel>
              )}

              {data.ai_score_trend.length > 0 && (
                <Panel
                  title="AI-writing estimate trend"
                  subtitle="Average completed classifier estimate over time; advisory, not proof of authorship"
                >
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={data.ai_score_trend}>
                        <CartesianGrid
                          stroke="#edf1f7"
                          strokeDasharray="3 3"
                          vertical={false}
                        />
                        <XAxis dataKey="date" tickFormatter={dateLabel} />
                        <YAxis
                          domain={[0, 100]}
                          tickFormatter={(value) => `${value}%`}
                        />
                        <Tooltip
                          contentStyle={tooltipStyle}
                          formatter={(value) => [
                            `${Number(value).toFixed(1)}%`,
                            "AI-writing estimate",
                          ]}
                        />
                        <Line
                          type="monotone"
                          dataKey="average_score"
                          name="AI-writing estimate"
                          stroke="#55a6d8"
                          strokeWidth={2.5}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </Panel>
              )}

              {data.department_ai_scores.length > 0 && (
                <Panel
                  title="Department AI comparison"
                  subtitle="Average classifier estimate by department"
                >
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={data.department_ai_scores}>
                        <CartesianGrid
                          stroke="#edf1f7"
                          strokeDasharray="3 3"
                          vertical={false}
                        />
                        <XAxis dataKey="name" />
                        <YAxis domain={[0, 100]} />
                        <Tooltip
                          contentStyle={tooltipStyle}
                          formatter={(value) => [
                            `${Number(value).toFixed(1)}%`,
                            "AI-writing estimate",
                          ]}
                        />
                        <Bar
                          dataKey="value"
                          name="AI-writing estimate"
                          fill="#55a6d8"
                          radius={[6, 6, 0, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </Panel>
              )}

            </div>
          </section>
        )}

        {/* Organization map */}
        <Panel
          title="Organization activity map"
          subtitle="Geographic document activity, when authorized location data is configured"
          action={
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-50 px-2.5 py-1.5 text-[10px] font-Arial semibold text-slate-500">
              <Activity size={12} />
              LOCATION DATA
            </span>
          }
        >
          {data.organization_locations.length > 0 ? (
            <OrganizationMap locations={data.organization_locations} />
          ) : (
            <EmptyState
              title="Location analytics not configured"
              description="The current scan records do not include organization coordinates. This panel will become available when location data is provided."
            />
          )}
        </Panel>

        {/* Recent activity */}
        <Panel
          title="Recent document activity"
          subtitle="Latest scans and their analysis signals. AI-writing estimates are advisory, not proof of authorship."
          action={
            <span className="rounded-lg bg-slate-50 px-2.5 py-1.5 text-[10px] font-Arial bold text-slate-500">
              {fmt(data.recent_scans.length)} RECORDS
            </span>
          }
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left">
              <thead>
                <tr className="border-b border-slate-100 text-[10px] font-Arialbold uppercase tracking-[0.12em] text-slate-400">
                  <th className="px-3 py-3.5">Document</th>
                  <th className="px-3 py-3.5">Department</th>
                  <th className="px-3 py-3.5">Similarity</th>
                  <th className="px-3 py-3.5">AI-writing estimate</th>
                  <th className="px-3 py-3.5">Processing status</th>
                  <th className="px-3 py-3.5">Scanned on</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.recent_scans.map((scan) => (
                  <tr
                    key={scan.id}
                    className="transition hover:bg-slate-50/80"
                  >
                    <td className="max-w-64 px-3 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
                          <FileText size={17} />
                        </div>
                        <div className="min-w-0">
                          <p
                            title={scan.title}
                            className="max-w-56 truncate text-xs font-Arial bold text-slate-800"
                          >
                            {scan.title}
                          </p>
                          <p className="mt-1 text-[10px] text-slate-400">
                            ID: {scan.id.slice(0, 8)}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-4 text-xs text-slate-500">
                      {scan.department ?? "—"}
                    </td>
                    <td className="px-3 py-4">
                      <span className="text-xs font-Arial bold text-slate-800">
                        {pct(scan.plagiarism_score)}
                      </span>
                    </td>
                    <td className="px-3 py-4 text-xs text-slate-500">
                      {scan.ai_score == null ? (
                        "Not available"
                      ) : (
                        <span title="Advisory classifier estimate; not proof of authorship.">
                          {pct(scan.ai_score)}
                          <small className="recent-score-confidence">
                            {scan.ai_confidence == null
                              ? "Confidence unavailable"
                              : `Model confidence ${pct(scan.ai_confidence * 100)}`}
                          </small>
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-4">
                      <StatusBadge status={scan.status} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-4 text-xs text-slate-500">
                      {scan.created_at
                        ? new Date(scan.created_at).toLocaleString("en-IN", {
                            day: "2-digit",
                            month: "short",
                            year: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "—"}
                    </td>
                  </tr>
                ))}

                {data.recent_scans.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-3 py-12">
                      {loading ? (
                        <div className="flex items-center justify-center gap-2 text-xs text-slate-500">
                          <RefreshCw size={15} className="animate-spin" />
                          Loading document records…
                        </div>
                      ) : (
                        <EmptyState
                          title="No recent documents"
                          description="No scan records were found in the selected period."
                        />
                      )}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Panel>

        {/* Footer */}
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200/80 py-5 text-[11px] text-slate-400">
          <div className="flex items-center gap-2">
            <ShieldCheck size={15} />
            <span>ASTE Insight · Administrative analytics</span>
          </div>
          <div className="flex items-center gap-3">
            <span>Reporting window: {days} days</span>
            <span className="hidden text-slate-300 sm:inline">|</span>
            <span>
              {data.generated_at
                ? `Updated ${new Date(data.generated_at).toLocaleString("en-IN")}`
                : "Waiting for API data"}
            </span>
          </div>
        </footer>
          </div>
        </details>
      </main>
      {activePreview && (
        <FilePreviewModal
          title={activePreview.title}
          fileName={activePreview.fileName}
          endpoint={activePreview.endpoint}
          onClose={() => setActivePreview(null)}
        />
      )}
    </div>
  );
}
