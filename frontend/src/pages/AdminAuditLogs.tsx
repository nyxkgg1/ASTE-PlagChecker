import { useState, type ChangeEvent, type FormEvent } from "react";
import { apiDownload, apiGet, buildQuery } from "../api/client";
import type { AuditLogRow, Paged } from "../api/types";
import { ErrorBox, Modal, formatDate } from "../components/ui";
import { toArray, useLoad } from "../lib/data";

const PAGE_SIZE = 20;

interface Filters {
  action: string;
  entity_type: string;
  user_id: string;
  start_date: string;
  end_date: string;
}

const EMPTY: Filters = { action: "", entity_type: "", user_id: "", start_date: "", end_date: "" };

// Include the full minute selected by datetime-local in the inclusive end filter.
const toIso = (value: string, endOfMinute = false) => {
  if (!value) return undefined;
  const date = new Date(value);
  if (endOfMinute) date.setMinutes(date.getMinutes() + 1, 0, -1);
  return date.toISOString();
};

export default function AdminAuditLogs() {
  const [draft, setDraft] = useState<Filters>(EMPTY);
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<AuditLogRow | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const { data, error, loading } = useLoad(
    () =>
      apiGet<Paged<AuditLogRow> | AuditLogRow[]>(
        `/admin/audit-logs${buildQuery({
          page,
          page_size: PAGE_SIZE,
          action: filters.action.trim(),
          entity_type: filters.entity_type.trim(),
          user_id: filters.user_id.trim(),
          start_date: toIso(filters.start_date),
          end_date: toIso(filters.end_date, true),
        })}`,
      ),
    [page, filters],
  );

  const rows = toArray<AuditLogRow>(data);
  const pagination = !Array.isArray(data) ? data?.pagination : undefined;
  const total = !Array.isArray(data)
    ? data?.total ?? pagination?.total
    : undefined;
  const totalPages = !Array.isArray(data)
    ? data?.total_pages ?? pagination?.total_pages
    : undefined;
  const hasNext = totalPages ? page < totalPages : rows.length === PAGE_SIZE;

  function apply(event: FormEvent) {
    event.preventDefault();
    setPage(1);
    setFilters({ ...draft });
  }

  const set = (key: keyof Filters) => (e: ChangeEvent<HTMLInputElement>) =>
    setDraft((d) => ({ ...d, [key]: e.target.value }));

  async function exportLogs(format: "pdf" | "xlsx" | "csv") {
    setExporting(format);
    setExportError(null);
    try {
      await apiDownload(
        `/admin/audit-logs/export${buildQuery({
          format,
          action: filters.action.trim(),
          entity_type: filters.entity_type.trim(),
          user_id: filters.user_id.trim(),
          start_date: toIso(filters.start_date),
          end_date: toIso(filters.end_date, true),
        })}`,
        `audit-logs.${format}`,
      );
    } catch (err) {
      setExportError(
        err instanceof Error ? err.message : "Audit logs could not be exported.",
      );
    } finally {
      setExporting(null);
    }
  }

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 14 }}>
        <h1 style={{ margin: 0 }}>Audit Logs</h1>
        <div className="row" style={{ gap: 8 }}>
          <button
            type="button"
            className="btn small ghost"
            disabled={Boolean(exporting)}
            onClick={() => void exportLogs("pdf")}
          >
            {exporting === "pdf" ? "Preparing PDF…" : "Download PDF"}
          </button>
          <button
            type="button"
            className="btn small ghost"
            disabled={Boolean(exporting)}
            onClick={() => void exportLogs("xlsx")}
          >
            {exporting === "xlsx" ? "Preparing Excel…" : "Download Excel"}
          </button>
          <button
            type="button"
            className="btn small ghost"
            disabled={Boolean(exporting)}
            onClick={() => void exportLogs("csv")}
          >
            {exporting === "csv" ? "Preparing CSV…" : "Download CSV"}
          </button>
        </div>
      </div>
      <form className="card row" style={{ marginBottom: 14 }} onSubmit={apply}>
        <label>
          Action
          <input value={draft.action} onChange={set("action")} placeholder="e.g. CERTIFICATE_VERIFIED" />
        </label>
        <label>
          Entity type
          <input value={draft.entity_type} onChange={set("entity_type")} placeholder="e.g. CERTIFICATE" />
        </label>
        <label>
          User ID
          <input value={draft.user_id} onChange={set("user_id")} placeholder="UUID" />
        </label>
        <label>
          From
          <input
            type="datetime-local"
            value={draft.start_date}
            onChange={set("start_date")}
            aria-label="Filter audit logs from date and time"
          />
        </label>
        <label>
          To
          <input
            type="datetime-local"
            value={draft.end_date}
            onChange={set("end_date")}
            aria-label="Filter audit logs through date and time"
          />
        </label>
        <button type="submit" className="btn">
          {loading ? "Applying…" : "Apply"}
        </button>
        <button
          type="button"
          className="btn ghost"
          onClick={() => {
            setDraft(EMPTY);
            setFilters(EMPTY);
            setPage(1);
          }}
        >
          Clear
        </button>
      </form>

      {loading && (
        <p className="muted" role="status" aria-live="polite">
          Loading audit events…
        </p>
      )}
      <ErrorBox message={error} />
      <ErrorBox message={exportError} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Action</th>
              <th>Entity</th>
              <th>User</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5}>Loading…</td>
              </tr>
            )}
            {!loading && rows.length === 0 && !error && (
              <tr>
                <td colSpan={5} className="muted">
                  No audit events match.
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{formatDate(row.created_at)}</td>
                <td className="left">{row.action}</td>
                <td>{row.entity_type ?? "—"}</td>
                <td className="muted">{row.user_name || "Unknown user"}</td>
                <td>
                  <button className="btn small ghost" onClick={() => setSelected(row)}>
                    Details
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="pager">
        {total !== undefined && <span className="muted">{total} events</span>}
        <button className="btn small ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
          Previous
        </button>
        <span>Page {page}</span>
        <button className="btn small ghost" disabled={!hasNext} onClick={() => setPage((p) => p + 1)}>
          Next
        </button>
      </div>

      {selected && (
        <Modal title="Audit event" onClose={() => setSelected(null)}>
          <pre className="json">{JSON.stringify(selected, null, 2)}</pre>
          <div className="btns">
            <button className="btn" onClick={() => setSelected(null)}>
              Close
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
