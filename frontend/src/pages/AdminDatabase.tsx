import { useState } from "react";
import type { FormEvent } from "react";
import { apiGet, apiSend, apiUpload } from "../api/client";
import type { ReferenceDocument, ReferenceRequest } from "../api/types";
import { ErrorBox, StatusPill, formatDate } from "../components/ui";
import FilePreviewModal from "../components/FilePreviewModal";
import { toArray, useLoad } from "../lib/data";

type Tab = "requests" | "documents";
type Decision = "APPROVED" | "REJECTED";

export default function AdminDatabase() {
  const [tab, setTab] = useState<Tab>("requests");

  return (
    <>
      <h1>Manage Database</h1>

      <div className="row" style={{ marginBottom: 14 }}>
        <button
          type="button"
          className={`btn${tab === "requests" ? "" : " ghost"}`}
          onClick={() => setTab("requests")}
        >
          Pending Approvals
        </button>

        <button
          type="button"
          className={`btn${tab === "documents" ? "" : " ghost"}`}
          onClick={() => setTab("documents")}
        >
          Manage Documents
        </button>
      </div>

      {tab === "requests" ? <Requests /> : <Documents />}
    </>
  );
}

function Requests() {
  const { data, error, loading, reload } = useLoad<unknown>(
    () => apiGet<unknown>("/admin/requests"),
    [],
  );

  const rows = toArray<ReferenceRequest>(data);

  const [actionError, setActionError] = useState<string | null>(null);
  const [rejectTarget, setRejectTarget] =
    useState<ReferenceRequest | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [preview, setPreview] = useState<{
    title: string;
    fileName: string;
    endpoint: string;
    textEndpoint: string;
  } | null>(null);

  async function submitReview(
    row: ReferenceRequest,
    decision: Decision,
    reason = "",
  ) {
    const trimmedReason = reason.trim();

    if (decision === "REJECTED" && !trimmedReason) {
      setActionError("Please enter a rejection reason.");
      return;
    }

    setReviewing(true);
    setActionError(null);

    try {
      await apiSend("PATCH", `/admin/requests/${row.id}/review`, {
        decision,
        rejection_reason:
          decision === "REJECTED" ? trimmedReason : null,
        admin_comments:
          decision === "REJECTED" ? trimmedReason : null,
      });

      setRejectTarget(null);
      setRejectionReason("");
      await reload();
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Review failed.",
      );
    } finally {
      setReviewing(false);
    }
  }

  function review(row: ReferenceRequest, decision: Decision) {
    setActionError(null);

    if (decision === "REJECTED") {
      setRejectionReason("");
      setRejectTarget(row);
      return;
    }

    const confirmed = window.confirm(
      `Approve the ${row.request_type ?? "reference"} request for "${row.title ?? "Untitled document"}"?`,
    );

    if (confirmed) {
      void submitReview(row, "APPROVED");
    }
  }

  return (
    <>
      <h2>Pending Approvals</h2>

      <ErrorBox message={error ?? actionError} />

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Sr No.</th>
              <th>Type</th>
              <th>Title</th>
              <th>Reason</th>
              <th>Requested</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>

          <tbody>
            {loading && (
              <tr>
                <td colSpan={7}>Loading…</td>
              </tr>
            )}

            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
                  No reference requests found.
                </td>
              </tr>
            )}

            {rows.map((row, index) => (
              <tr key={row.id}>
                <td>{index + 1}</td>
                <td>{row.request_type ?? "—"}</td>
                <td className="left">{row.title ?? "—"}</td>
                <td className="left">{row.reason ?? "—"}</td>
                <td>{formatDate(row.created_at)}</td>
                <td>
                  <StatusPill status={row.status} />
                </td>
                <td>
                  <div
                    className="row"
                    style={{ justifyContent: "center", gap: 6 }}
                  >
                    {row.request_type === "ADD" &&
                      row.pending_file_name && (
                        <button
                          type="button"
                          className="btn small ghost"
                          onClick={() => {
                            setActionError(null);
                            setPreview({
                              title: row.title || "Reference request",
                              fileName: row.pending_file_name!,
                              endpoint: `/admin/requests/${encodeURIComponent(row.id)}/file`,
                              textEndpoint: `/admin/requests/${encodeURIComponent(row.id)}/preview`,
                            });
                          }}
                        >
                          Preview file
                        </button>
                      )}

                    {row.status === "PENDING" && (
                      <>
                        <button
                          type="button"
                          className="btn small green"
                          disabled={reviewing}
                          onClick={() => review(row, "APPROVED")}
                        >
                          Approve
                        </button>

                        <button
                          type="button"
                          className="btn small red"
                          disabled={reviewing}
                          onClick={() => review(row, "REJECTED")}
                        >
                          Reject
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rejectTarget && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 16,
            background: "rgba(0, 0, 0, 0.6)",
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="reject-request-title"
            style={{
              width: "100%",
              maxWidth: 480,
              padding: 24,
              borderRadius: 12,
              background: "var(--card-bg, white)",
              color: "var(--text-color, #222)",
              boxShadow: "0 12px 40px rgba(0,0,0,0.25)",
            }}
          >
            <h2 id="reject-request-title">
              Reject reference request
            </h2>

            <p>{rejectTarget.title ?? "Untitled document"}</p>

            <label htmlFor="reference-rejection-reason">
              Rejection reason
            </label>

            <textarea
              id="reference-rejection-reason"
              value={rejectionReason}
              onChange={(event) => setRejectionReason(event.target.value)}
              rows={4}
              maxLength={2000}
              placeholder="Explain why this request is being rejected..."
              style={{
                display: "block",
                boxSizing: "border-box",
                width: "100%",
                marginTop: 8,
                marginBottom: 16,
                padding: 10,
              }}
            />

            <div
              className="row"
              style={{ justifyContent: "flex-end", gap: 8 }}
            >
              <button
                type="button"
                className="btn small ghost"
                disabled={reviewing}
                onClick={() => {
                  setRejectTarget(null);
                  setRejectionReason("");
                  setActionError(null);
                }}
              >
                Cancel
              </button>

              <button
                type="button"
                className="btn small red"
                disabled={reviewing || !rejectionReason.trim()}
                onClick={() =>
                  void submitReview(
                    rejectTarget,
                    "REJECTED",
                    rejectionReason,
                  )
                }
              >
                {reviewing ? "Saving…" : "Confirm rejection"}
              </button>
            </div>
          </div>
        </div>
      )}
      {preview && (
        <FilePreviewModal
          {...preview}
          onClose={() => setPreview(null)}
        />
      )}
    </>
  );
}

function Documents() {
  const { data, error, loading, reload } = useLoad<unknown>(
    () => apiGet<unknown>("/reference"),
    [],
  );

  const rows = toArray<ReferenceDocument>(data);

  const [actionError, setActionError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [indexing, setIndexing] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [title, setTitle] = useState("");
  const [documentType, setDocumentType] = useState("FTER");
  const [preview, setPreview] = useState<{
    title: string;
    fileName: string;
    endpoint: string;
    textEndpoint: string;
  } | null>(null);

  async function uploadReference(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const formElement = event.currentTarget;
    const fileInput = formElement.querySelector<HTMLInputElement>(
      'input[name="reference-file"]',
    );
    const file = fileInput?.files?.[0];

    if (!title.trim() || !file) {
      setActionError("Please enter a title and select a document.");
      return;
    }

    const form = new FormData();
    form.append("title", title.trim());
    form.append("document_type", documentType);
    form.append("file", file);

    setUploading(true);
    setActionError(null);
    setSuccessMessage(null);

    try {
      await apiUpload("/admin/references", form);

      setSuccessMessage("Reference uploaded and indexed successfully.");
      setTitle("");
      setDocumentType("FTER");
      formElement.reset();
      await reload();
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Reference upload failed.",
      );
    } finally {
      setUploading(false);
    }
  }

  async function reindex(id: string) {
    setIndexing(id);
    setActionError(null);
    setSuccessMessage(null);

    try {
      await apiSend("POST", `/reference/${encodeURIComponent(id)}/index`);
      setSuccessMessage("Reference re-indexed successfully.");
      await reload();
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Indexing failed.",
      );
    } finally {
      setIndexing(null);
    }
  }

  async function deleteReference(row: ReferenceDocument) {
    const confirmed = window.confirm(
      `Remove “${row.title}” from the reference collection? It will no longer be used for future matching. The file and version history will be retained for audit purposes.`,
    );
    if (!confirmed) return;

    setDeleting(row.id);
    setActionError(null);
    setSuccessMessage(null);

    try {
      await apiSend(
        "DELETE",
        `/reference/${encodeURIComponent(row.id)}`,
      );
      setSuccessMessage("Reference document removed from the collection.");
      await reload();
    } catch (err) {
      setActionError(
        err instanceof Error
          ? err.message
          : "Reference document could not be deleted.",
      );
    } finally {
      setDeleting(null);
    }
  }

  return (
    <>
      <h2>Add Reference Document</h2>

      <form
        onSubmit={uploadReference}
        className="column"
        style={{
          gap: 12,
          maxWidth: 560,
          marginBottom: 24,
          padding: 16,
          border: "1px solid var(--border, #ccc)",
          borderRadius: 8,
        }}
      >
        <label>
          Document Title
          <input
            type="text"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Enter reference document title"
            required
            maxLength={255}
            disabled={uploading}
          />
        </label>

        <label>
          Document Type
          <select
            value={documentType}
            onChange={(event) => setDocumentType(event.target.value)}
            disabled={uploading}
          >
            <option value="FTER">FTER</option>
          </select>
        </label>

        <label>
          Select Document
          <input
            name="reference-file"
            type="file"
            accept=".pdf,.doc,.docx,.txt"
            required
            disabled={uploading}
          />
        </label>

        <button className="btn" type="submit" disabled={uploading}>
          {uploading
            ? "Uploading and indexing…"
            : "Add to Reference Database"}
        </button>
      </form>

      <ErrorBox message={error ?? actionError} />

      {successMessage && <p role="status">{successMessage}</p>}

      <h2>Manage Documents</h2>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Sr No.</th>
              <th>Title</th>
              <th>Type</th>
              <th>Version</th>
              <th>Status</th>
              <th>Saved On</th>
              <th>Actions</th>
            </tr>
          </thead>

          <tbody>
            {loading && (
              <tr>
                <td colSpan={7}>Loading…</td>
              </tr>
            )}

            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
                  No reference documents found.
                </td>
              </tr>
            )}

            {rows.map((row, index) => (
              <tr key={row.id}>
                <td>{index + 1}</td>
                <td className="left">{row.title}</td>
                <td>{row.document_type ?? "—"}</td>
                <td>{row.current_version ?? "—"}</td>
                <td>
                  <StatusPill status={row.status} />
                </td>
                <td>{formatDate(row.created_at)}</td>
                <td>
                  <div
                    className="row"
                    style={{ justifyContent: "center", gap: 6 }}
                  >
                    {row.file_name && (
                      <button
                        type="button"
                        className="btn small ghost"
                        onClick={() =>
                          setPreview({
                            title: row.title,
                            fileName: row.file_name!,
                            endpoint: `/reference/${encodeURIComponent(row.id)}/document`,
                            textEndpoint: `/reference/${encodeURIComponent(row.id)}/preview`,
                          })
                        }
                      >
                        Preview
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn small ghost"
                      disabled={indexing === row.id || deleting === row.id}
                      onClick={() => void reindex(row.id)}
                    >
                      {indexing === row.id ? "Indexing…" : "Re-index"}
                    </button>

                    <button
                      type="button"
                      className="btn small red"
                      disabled={indexing === row.id || deleting === row.id}
                      onClick={() => void deleteReference(row)}
                    >
                      {deleting === row.id ? "Removing…" : "Delete"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {preview && (
        <FilePreviewModal
          {...preview}
          onClose={() => setPreview(null)}
        />
      )}
    </>
  );
}
