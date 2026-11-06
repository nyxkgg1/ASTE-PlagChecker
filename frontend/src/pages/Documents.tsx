import { useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { apiDownload, apiGet, apiSend, apiUpload } from "../api/client";
import type { CertificateRow, ReferenceRequest } from "../api/types";
import { ErrorBox, formatDate, Modal, StatusPill } from "../components/ui";
import { useAuth } from "../auth/AuthContext";
import {
  pick,
  pickString,
  percentageValue,
  toArray,
  useLoad,
} from "../lib/data";

type Row = Record<string, unknown>;

export default function Documents() {
  const { hasRole } = useAuth();
  const isAdmin = hasRole("ADMIN");
  const isInstructor = hasRole("INSTRUCTOR");
  const navigate = useNavigate();
  const showStatus = hasRole("INSTRUCTOR", "STUDENT_OFFICER");
  const showActions = isAdmin || isInstructor;
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploadTarget, setUploadTarget] = useState<Row | null>(null);
  const [requestReason, setRequestReason] = useState("");
  const [requestOpen, setRequestOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [certificateTarget, setCertificateTarget] = useState<Row | null>(null);
  const [certificateDetails, setCertificateDetails] = useState({
    student_name: "",
    service_number: "",
    course: "",
    batch: "",
  });
  const [generatingCertificate, setGeneratingCertificate] = useState(false);

  const { data, error, loading, reload } = useLoad<unknown>(
    () => apiGet<unknown>("/scans"),
    [],
  );
  const {
    data: requestData,
    error: requestError,
  } = useLoad<unknown>(
    () =>
      isInstructor
        ? apiGet<unknown>("/reference/requests/my")
        : Promise.resolve([]),
    [isInstructor],
  );

  const rows = toArray<Row>(data);
  const requests = toArray<ReferenceRequest>(requestData);
  const [actionError, setActionError] = useState<string | null>(null);

  const columnCount = 6 + Number(showStatus) + Number(showActions);

  function chooseUpload(row: Row) {
    setActionError(null);
    setUploadTarget(row);
    if (isInstructor) {
      setRequestReason("");
      setRequestOpen(true);
      return;
    }
    if (fileInput.current) {
      fileInput.current.value = "";
      fileInput.current.click();
    }
  }

  async function handleUploadFile(file: File | undefined) {
    if (!file || !uploadTarget) return;

    if (!/\.(pdf|docx|txt)$/i.test(file.name)) {
      setActionError("Choose a PDF, DOCX, or TXT file.");
      setUploadTarget(null);
      return;
    }

    const form = new FormData();
    form.append("title", pickString(uploadTarget, "title"));
    form.append("document_type", "FTER");
    form.append("file", file);
    setUploading(true);
    setActionError(null);
    try {
      await apiUpload("/admin/references", form);
      await reload();
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Document upload failed.",
      );
    } finally {
      setUploading(false);
      setUploadTarget(null);
    }
  }

  async function submitUploadRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const scanId = pickString(uploadTarget ?? {}, "id");
    if (!scanId) {
      setActionError("This document has no scan ID.");
      return;
    }

    const form = new FormData();
    form.append("reason", requestReason.trim());
    setUploading(true);
    setActionError(null);
    try {
      await apiUpload(
        `/reference/requests/scans/${encodeURIComponent(scanId)}`,
        form,
      );
      setRequestOpen(false);
      setUploadTarget(null);
      await reload();
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Upload request failed.",
      );
    } finally {
      setUploading(false);
    }
  }

  async function generateCertificate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const scanId = pickString(certificateTarget ?? {}, "id");
    if (!scanId) {
      setActionError("This document has no scan ID.");
      return;
    }
    if (!certificateDetails.student_name.trim()) {
      setActionError("Student officer name is required.");
      return;
    }

    setGeneratingCertificate(true);
    setActionError(null);
    try {
      await apiSend<CertificateRow>(
        "POST",
        `/scans/${encodeURIComponent(scanId)}/certificate`,
        {
          student_name: certificateDetails.student_name.trim(),
          service_number: certificateDetails.service_number.trim() || null,
          course: certificateDetails.course.trim() || null,
          batch: certificateDetails.batch.trim() || null,
        },
      );
      setCertificateTarget(null);
      setCertificateDetails({
        student_name: "",
        service_number: "",
        course: "",
        batch: "",
      });
      await reload();
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Could not generate certificate.",
      );
    } finally {
      setGeneratingCertificate(false);
    }
  }

  function openComparison(row: Row) {
    const id = pickString(row, "id");
    if (!id) {
      setActionError("This document has no scan ID.");
      return;
    }
    navigate(`/scan?scanId=${encodeURIComponent(id)}`);
  }

  return (
    <>
      <h1>Previous Documents</h1>

      <p className="muted">
        View your scanned-document history, results, and available certificates.
        AI-writing estimates are advisory indicators, not proof of authorship.
      </p>

      <ErrorBox message={error || requestError || actionError} />

      {showActions && (
        <input
          ref={fileInput}
          type="file"
          accept=".pdf,.docx,.txt"
          hidden
          onChange={(event) => void handleUploadFile(event.target.files?.[0])}
        />
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Sr No.</th>
              <th>Title</th>
              {showStatus && <th>Status</th>}
              <th>Scanned On</th>
              <th>Certificate Generated</th>
              <th>Plagiarism Score</th>
              <th>AI-writing estimate</th>
              {showActions && <th>Actions</th>}
            </tr>
          </thead>

          <tbody>
            {loading && (
              <tr>
                <td colSpan={columnCount}>Loading…</td>
              </tr>
            )}

            {!loading && rows.length === 0 && !error && (
              <tr>
                <td colSpan={columnCount} className="muted">
                  No documents scanned yet.
                </td>
              </tr>
            )}

            {rows.map((row, index) => {
              const id = String(row.id ?? "");

              const hasCertificate =
                row.certificate_generated === true ||
                Boolean(
                  pick(row, "certificate_number", "certificate_id"),
                );

              const plagiarism = percentageValue(
                pick(row, "plagiarism_score", "overall_similarity"),
              );
              const ai = percentageValue(row.ai_score);
              const aiConfidence =
                typeof row.ai_confidence === "number"
                  ? percentageValue(row.ai_confidence * 100)
                  : null;
              const scanRequest = isInstructor
                ? requests.find(
                    (request) =>
                      request.request_type?.toUpperCase() === "ADD" &&
                      (request.scan_id === id ||
                        (!request.scan_id &&
                          request.title === pickString(row, "title"))),
                  )
                : undefined;
              const approvalStatus = (
                scanRequest?.status ??
                pickString(row, "reference_request_status")
              ).toUpperCase();
              const displayStatus =
                approvalStatus === "PENDING"
                  ? "Pending"
                  : approvalStatus === "APPROVED"
                    ? "Approved"
                    : approvalStatus === "REJECTED"
                      ? "Rejected"
                        : "-";

              return (
                <tr key={id || index}>
                  <td>{index + 1}</td>

                  <td className="left">
                    {pickString(row, "title") || "—"}
                  </td>

                  {showStatus && (
                    <td>
                      {displayStatus === "-" ? (
                        <span className="pill grey">-</span>
                      ) : (
                        <StatusPill status={displayStatus} />
                      )}
                    </td>
                  )}

                  <td>
                    {formatDate(
                      pickString(row, "created_at", "scanned_on") || null,
                    )}
                  </td>

                  <td>
                    <span
                      className={`pill ${hasCertificate ? "green" : "red"}`}
                    >
                      {hasCertificate ? "Yes" : "No"}
                    </span>
                  </td>

                  <td>
                    {plagiarism === null ? "—" : `${plagiarism}%`}
                  </td>

                  <td>
                    {ai === null ? (
                      "Not available"
                    ) : (
                      <span title="Advisory classifier estimate; not proof of authorship.">
                        {ai.toFixed(1)}%
                        <small className="muted score-confidence">
                          {aiConfidence === null
                            ? "Model confidence unavailable"
                            : `Model confidence ${aiConfidence.toFixed(1)}%`}
                        </small>
                      </span>
                    )}
                  </td>

                  {showActions && (
                    <td>
                      <div className="row" style={{ justifyContent: "center", gap: 6, flexWrap: "wrap" }}>
                        <button
                          type="button"
                          className="btn small ghost"
                          disabled={uploading || (isInstructor && !!scanRequest)}
                          onClick={() => chooseUpload(row)}
                        >
                          {isAdmin
                            ? "Upload to DB"
                            : scanRequest
                              ? "Requested"
                              : "Request Upload"}
                        </button>
                        <button
                          type="button"
                          className="btn small ghost"
                          onClick={() => openComparison(row)}
                        >
                          Open Scan Page
                        </button>
                        {hasCertificate ? (
                          <button
                            type="button"
                            className="btn small ghost"
                            disabled={!id}
                            onClick={() => {
                              setActionError(null);
                              apiDownload(
                                `/scans/${encodeURIComponent(id)}/certificate/download`,
                                "certificate.pdf",
                              ).catch((err: unknown) => {
                                setActionError(
                                  err instanceof Error
                                    ? err.message
                                    : "Certificate download failed.",
                                );
                              });
                            }}
                          >
                            Download Certificate
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="btn small ghost"
                            disabled={!id || generatingCertificate}
                            onClick={() => {
                              setActionError(null);
                              setCertificateDetails({
                                student_name: "",
                                service_number: "",
                                course: "",
                                batch: "",
                              });
                              setCertificateTarget(row);
                            }}
                          >
                            Generate Certificate
                          </button>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {requestOpen && uploadTarget && (
        <Modal
          title="Request Upload"
          onClose={() => {
            if (!uploading) setRequestOpen(false);
          }}
        >
          <form onSubmit={(event) => void submitUploadRequest(event)}>
            <ErrorBox message={actionError} />
            <p className="muted">
              Request administrator approval to add the scanned document “{pickString(uploadTarget, "title")}” to the Document Manager.
            </p>
            <label>
              Reason
              <textarea
                rows={3}
                maxLength={2000}
                required
                value={requestReason}
                onChange={(event) => setRequestReason(event.target.value)}
              />
            </label>
            <div className="btns">
              <button
                type="button"
                className="btn ghost"
                disabled={uploading}
                onClick={() => setRequestOpen(false)}
              >
                Cancel
              </button>
              <button type="submit" className="btn" disabled={uploading}>
                {uploading ? "Sending…" : "Send Request"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {certificateTarget && (
        <Modal
          title="Generate Certificate"
          onClose={() => {
            if (!generatingCertificate) setCertificateTarget(null);
          }}
        >
          <form
            className="column"
            onSubmit={(event) => void generateCertificate(event)}
            style={{ gap: 12 }}
          >
            <ErrorBox message={actionError} />
            <p className="muted">
              Certificate for “{pickString(certificateTarget, "title")}”.
            </p>
            <label>
              Student officer name
              <input
                required
                maxLength={255}
                value={certificateDetails.student_name}
                onChange={(event) =>
                  setCertificateDetails((details) => ({
                    ...details,
                    student_name: event.target.value,
                  }))
                }
              />
            </label>
            <label>
              Service number
              <input
                maxLength={100}
                value={certificateDetails.service_number}
                onChange={(event) =>
                  setCertificateDetails((details) => ({
                    ...details,
                    service_number: event.target.value,
                  }))
                }
              />
            </label>
            <label>
              Course
              <input
                maxLength={255}
                value={certificateDetails.course}
                onChange={(event) =>
                  setCertificateDetails((details) => ({
                    ...details,
                    course: event.target.value,
                  }))
                }
              />
            </label>
            <label>
              Batch
              <input
                maxLength={100}
                value={certificateDetails.batch}
                onChange={(event) =>
                  setCertificateDetails((details) => ({
                    ...details,
                    batch: event.target.value,
                  }))
                }
              />
            </label>
            <div className="btns">
              <button
                type="button"
                className="btn ghost"
                disabled={generatingCertificate}
                onClick={() => setCertificateTarget(null)}
              >
                Cancel
              </button>
              <button type="submit" className="btn" disabled={generatingCertificate}>
                {generatingCertificate ? "Generating…" : "Generate Certificate"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
