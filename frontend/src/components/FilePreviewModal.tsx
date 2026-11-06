import { lazy, Suspense, useEffect, useState } from "react";
import { Download, FileText, LoaderCircle, ShieldCheck, X } from "lucide-react";
import { apiDownload, apiGetBlob } from "../api/client";

const PdfDocumentPreview = lazy(() => import("./PdfDocumentPreview"));

type FilePreviewModalProps = {
  title: string;
  fileName: string;
  endpoint: string;
  textEndpoint?: string;
  onClose: () => void;
};

export default function FilePreviewModal({
  title,
  fileName,
  endpoint,
  textEndpoint,
  onClose,
}: FilePreviewModalProps) {
  const [fileBlob, setFileBlob] = useState<Blob | null>(null);
  const [textContent, setTextContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const isDocx = /\.docx$/i.test(fileName);
  const supported =
    /\.(pdf|txt)$/i.test(fileName) || (isDocx && Boolean(textEndpoint));

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    let active = true;
    setFileBlob(null);
    setTextContent(null);
    setError("");

    if (!supported) {
      setLoading(false);
      return () => {
        active = false;
      };
    }

    setLoading(true);
    const previewEndpoint = isDocx ? textEndpoint : endpoint;
    if (!previewEndpoint) {
      setLoading(false);
      return () => {
        active = false;
      };
    }

    void apiGetBlob(previewEndpoint)
      .then(async (blob) => {
        if (blob.size === 0) {
          throw new Error("The document file is empty.");
        }
        if (!active) return;
        if (/\.pdf$/i.test(fileName)) {
          setFileBlob(blob);
        } else {
          const text = await blob.text();
          if (active) setTextContent(text);
        }
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(
            cause instanceof Error
              ? cause.message
              : "This document preview could not be loaded.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [endpoint, fileName, supported, isDocx, textEndpoint]);

  async function downloadFile() {
    setDownloading(true);
    setDownloadError("");
    try {
      await apiDownload(endpoint, fileName);
    } catch (cause) {
      setDownloadError(
        cause instanceof Error ? cause.message : "The document could not be downloaded.",
      );
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div
      className="file-preview-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="file-preview-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={`Preview ${title}`}
      >
        <header className="file-preview-header">
          <div className="file-preview-heading">
            <span className="file-preview-icon">
              <FileText size={19} />
            </span>
            <div className="min-w-0">
              <h2 title={title}>{title}</h2>
              <p title={fileName}>{fileName}</p>
            </div>
          </div>
          <div className="file-preview-actions">
            <button
              type="button"
              className="file-preview-download"
              onClick={() => void downloadFile()}
              disabled={downloading}
            >
              {downloading ? (
                <LoaderCircle size={15} className="animate-spin" />
              ) : (
                <Download size={15} />
              )}
              {downloading ? "Preparing…" : "Download"}
            </button>
            <button
              type="button"
              className="file-preview-close"
              onClick={onClose}
              aria-label="Close preview"
            >
              <X size={19} />
            </button>
          </div>
        </header>

        {downloadError && (
          <p className="file-preview-download-error" role="alert">
            {downloadError}
          </p>
        )}

        <div className="file-preview-body">
          {loading && (
            <div className="file-preview-loading" role="status">
              <div className="file-preview-loader-orbit">
                <span />
                <ShieldCheck size={24} />
              </div>
              <p>Preparing your secure preview…</p>
              <div className="file-preview-skeleton">
                <span />
                <span />
                <span />
                <span />
              </div>
            </div>
          )}

          {!loading && error && (
            <div className="file-preview-message file-preview-error" role="alert">
              <p>Preview unavailable</p>
              <span>{error}</span>
            </div>
          )}

          {!loading && !error && !supported && (
            <div className="file-preview-message">
              <span className="file-preview-icon">
                <FileText size={22} />
              </span>
              <p>Preview isn’t available for this file type yet.</p>
              <span>
                Download the original document to open it in a compatible app.
              </span>
            </div>
          )}

          {!loading && !error && fileBlob && /\.pdf$/i.test(fileName) && (
            <Suspense
              fallback={
                <div className="pdf-preview-status" role="status">
                  Starting secure PDF preview…
                </div>
              }
            >
              <PdfDocumentPreview file={fileBlob} title={title} />
            </Suspense>
          )}

          {!loading && !error && textContent !== null && supported && (
            <pre className="file-preview-text">{textContent || "This text file is empty."}</pre>
          )}
        </div>
      </section>
    </div>
  );
}
