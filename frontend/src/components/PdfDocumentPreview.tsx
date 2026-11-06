import { useEffect, useRef, useState } from "react";
import {
  getDocument,
  GlobalWorkerOptions,
  type PDFDocumentProxy,
  type PDFDocumentLoadingTask,
  type PDFPageProxy,
  type RenderTask,
} from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

export default function PdfDocumentPreview({
  file,
  title,
}: {
  file: Blob;
  title: string;
}) {
  const [documentProxy, setDocumentProxy] =
    useState<PDFDocumentProxy | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    let loadingTask: PDFDocumentLoadingTask | null = null;

    setDocumentProxy(null);
    setLoading(true);
    setError("");

    void file
      .arrayBuffer()
      .then((data) => {
        if (!active) return null;
        const task = getDocument({ data });
        loadingTask = task;
        return task.promise;
      })
      .then((pdf) => {
        if (!pdf) return;
        if (!active) {
          void pdf.destroy();
          return;
        }
        setDocumentProxy(pdf);
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(
            cause instanceof Error
              ? cause.message
              : "The PDF could not be opened.",
          );
          setLoading(false);
        }
      });

    return () => {
      active = false;
      if (loadingTask) void loadingTask.destroy();
    };
  }, [file]);

  return (
    <div className="pdf-preview-root">
      {loading && (
        <div className="pdf-preview-status" role="status">
          Preparing pages…
        </div>
      )}
      {error && (
        <div className="pdf-preview-status pdf-preview-error" role="alert">
          <strong>This PDF could not be displayed.</strong>
          <span>{error}</span>
        </div>
      )}
      {documentProxy && (
        <div className="pdf-preview-pages" aria-label={`Pages of ${title}`}>
          {Array.from({ length: documentProxy.numPages }, (_, index) => (
            <PdfPage
              key={`${index + 1}-${documentProxy.fingerprints[0]}`}
              documentProxy={documentProxy}
              pageNumber={index + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function PdfPage({
  documentProxy,
  pageNumber,
}: {
  documentProxy: PDFDocumentProxy;
  pageNumber: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [pageWidth, setPageWidth] = useState(0);
  const [pageHeight, setPageHeight] = useState<number | null>(null);
  const [rendered, setRendered] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      setPageWidth(entries[0]?.contentRect.width ?? 0);
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !pageWidth) return;

    let active = true;
    let renderTask: RenderTask | null = null;
    const renderPage = async () => {
      try {
        const page: PDFPageProxy = await documentProxy.getPage(pageNumber);
        const baseViewport = page.getViewport({ scale: 1 });
        const scale = Math.min(1.4, (pageWidth - 28) / baseViewport.width);
        const viewport = page.getViewport({ scale: Math.max(scale, 0.1) });
        if (!active || !canvasRef.current) return;

        const canvas = canvasRef.current;
        const context = canvas.getContext("2d");
        if (!context) throw new Error("Canvas rendering is unavailable.");

        const outputScale = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = Math.ceil(viewport.width * outputScale);
        canvas.height = Math.ceil(viewport.height * outputScale);
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;
        setPageHeight(viewport.height);

        renderTask = page.render({
          canvasContext: context,
          viewport,
          transform:
            outputScale === 1
              ? undefined
              : [outputScale, 0, 0, outputScale, 0, 0],
        });
        await renderTask.promise;
        if (active) setRendered(true);
      } catch (cause: unknown) {
        if (active) {
          setError(
            cause instanceof Error
              ? cause.message
              : "This page could not be rendered.",
          );
        }
      }
    };

    let started = false;
    const intersectionObserver = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting) && !started) {
          started = true;
          intersectionObserver.disconnect();
          void renderPage();
        }
      },
      { rootMargin: "700px 0px" },
    );
    intersectionObserver.observe(container);

    return () => {
      active = false;
      intersectionObserver.disconnect();
      renderTask?.cancel();
    };
  }, [documentProxy, pageNumber, pageWidth]);

  return (
    <section
      ref={containerRef}
      className="pdf-preview-page"
      aria-label={`Page ${pageNumber}`}
      style={{ minHeight: pageHeight ?? 900 }}
    >
      {!rendered && !error && (
        <span className="pdf-preview-page-loading">
          Loading page {pageNumber}…
        </span>
      )}
      {error ? (
        <span className="pdf-preview-page-error">
          Page {pageNumber} could not be displayed.
        </span>
      ) : (
        <canvas
          ref={canvasRef}
          className="pdf-preview-canvas"
          aria-label={`PDF page ${pageNumber}`}
        />
      )}
    </section>
  );
}
