import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  LoaderCircle,
  ShieldCheck,
} from "lucide-react";
import { apiDownload, apiGet } from "../api/client";
import type { CertificateRow } from "../api/types";
import FilePreviewModal from "../components/FilePreviewModal";
import { ErrorBox, Modal, StatusPill, formatDate } from "../components/ui";
import { percentageValue, toArray, useLoad } from "../lib/data";

type VerificationResponse = {
  verification_status?: string;
  integrity_valid?: boolean | null;
  message?: string;
};

type VerificationState = {
  number: string;
  loading: boolean;
  result?: VerificationResponse;
  error?: string;
};

export default function AdminCertificates() {
  const { data, error, loading } = useLoad(() => apiGet<unknown>("/admin/certificates"), []);
  const rows = toArray<CertificateRow>(data);
  const [actionError, setActionError] = useState<string | null>(null);
  const [verification, setVerification] = useState<VerificationState | null>(null);
  const [preview, setPreview] = useState<CertificateRow | null>(null);

  async function verify(row: CertificateRow) {
    setActionError(null);
    setVerification({ number: row.certificate_number, loading: true });
    try {
      const result = await apiGet<VerificationResponse>(
        `/admin/certificates/verify/${encodeURIComponent(row.certificate_number)}`,
      );
      setVerification({
        number: row.certificate_number,
        loading: false,
        result,
      });
    } catch (err) {
      setVerification({
        number: row.certificate_number,
        loading: false,
        error: err instanceof Error ? err.message : "Verification failed",
      });
    }
  }

  const verificationValid =
    verification?.result?.verification_status === "VERIFIED" &&
    verification.result.integrity_valid === true;
  const verificationFailed =
    verification?.result?.integrity_valid === false ||
    (verification?.result?.verification_status !== undefined &&
      verification.result.verification_status !== "VERIFIED" &&
      verification.result.verification_status !== "UNVERIFIABLE");

  return (
    <>
      <h1>Certificates</h1>
      <p className="muted">
        AI-writing estimates are advisory model indicators, not proof of who
        authored a document. Model confidence is not independently validated
        accuracy.
      </p>
      <ErrorBox message={error ?? actionError} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Sr No.</th>
              <th>Certificate No.</th>
              <th>Document</th>
              <th>Student Officer</th>
              <th>Plagiarism</th>
              <th>AI-writing estimate</th>
              <th>Generated</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={9}>
                  <div className="certificate-list-loading" role="status">
                    <LoaderCircle size={17} className="animate-spin" />
                    <span>Loading certificates…</span>
                    <i />
                    <i />
                    <i />
                  </div>
                </td>
              </tr>
            )}
            {!loading && rows.length === 0 && !error && (
              <tr>
                <td colSpan={9} className="muted">
                  No certificates generated yet.
                </td>
              </tr>
            )}
            {rows.map((row, index) => {
              const plag = percentageValue(row.plagiarism_score_percent);
              const ai = percentageValue(row.ai_score);
              const aiConfidence =
                typeof row.ai_confidence === "number"
                  ? percentageValue(row.ai_confidence * 100)
                  : null;
              return (
                <tr key={row.id}>
                  <td>{index + 1}</td>
                  <td className="left">{row.certificate_number}</td>
                  <td className="left">{row.document_title ?? "—"}</td>
                  <td className="left">{row.user?.full_name ?? row.user?.username ?? "—"}</td>
                  <td>{plag === null ? "—" : `${plag}%`}</td>
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
                  <td>{formatDate(row.generated_at)}</td>
                  <td>
                    <StatusPill status={row.status} />
                  </td>
                  <td>
                    <div className="row" style={{ justifyContent: "center", gap: 6 }}>
                      <button
                        className="btn small ghost"
                        onClick={() => void verify(row)}
                        disabled={verification?.loading}
                      >
                        {verification?.loading &&
                        verification.number === row.certificate_number ? (
                          <LoaderCircle size={13} className="animate-spin" />
                        ) : (
                          <ShieldCheck size={13} />
                        )}
                        Verify
                      </button>
                      <button
                        className="btn small ghost"
                        onClick={() => setPreview(row)}
                      >
                        <Eye size={13} />
                        Preview
                      </button>
                      <button
                        className="btn small"
                        onClick={() =>
                          apiDownload(`/admin/certificates/${row.id}/download`, `${row.certificate_number}.pdf`).catch(
                            (e) => setActionError(e instanceof Error ? e.message : "Download failed"),
                          )
                        }
                      >
                        Download
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {verification && (
        <Modal
          title={`Certificate verification`}
          onClose={() => setVerification(null)}
        >
          <div
            className={`certificate-verify-result ${
              verification.loading
                ? "is-checking"
                : verification.error || verificationFailed
                  ? "is-invalid"
                  : verificationValid
                    ? "is-valid"
                    : "is-unavailable"
            }`}
            role="status"
            aria-live="polite"
          >
            <div className="certificate-verify-mark">
              {verification.loading ? (
                <LoaderCircle size={28} className="animate-spin" />
              ) : verification.error || verificationFailed ? (
                <AlertTriangle size={28} />
              ) : verificationValid ? (
                <CheckCircle2 size={28} />
              ) : (
                <ShieldCheck size={28} />
              )}
            </div>
            <p className="certificate-verify-title">
              {verification.loading
                ? "Checking certificate integrity"
                : verification.error
                  ? "Verification could not be completed"
                  : verificationValid
                    ? "Certificate verified"
                    : verificationFailed
                      ? "Certificate could not be verified"
                      : "Integrity could not be confirmed"}
            </p>
            <p className="certificate-verify-description">
              {verification.loading
                ? "Comparing the saved certificate with its recorded security fingerprint."
                : verification.error ??
                  verification.result?.message ??
                  "No verification details were returned."}
            </p>
            <div className="certificate-verify-number">
              Certificate number <strong>{verification.number}</strong>
            </div>
          </div>
          <div className="btns">
            <button className="btn" onClick={() => setVerification(null)}>
              Close
            </button>
          </div>
        </Modal>
      )}
      {preview && (
        <FilePreviewModal
          title={preview.document_title || preview.certificate_number}
          fileName={`${preview.certificate_number}.pdf`}
          endpoint={`/admin/certificates/${encodeURIComponent(preview.id)}/download`}
          onClose={() => setPreview(null)}
        />
      )}
    </>
  );
}
