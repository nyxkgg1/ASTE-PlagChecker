import { useCallback, useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { ScanSearch, Sparkles } from "lucide-react";
import { apiDownload, apiGet, apiSend, apiUpload } from "../api/client";
import type {
  AIAnalysisResponse,
  CertificateRow,
  PlagiarismResult,
  ScanResponse,
} from "../api/types";
import { ErrorBox, Modal } from "../components/ui";
import {
  percentageValue,
  pickString,
  scoreToPercent,
  toArray,
} from "../lib/data";

type Row = Record<string, unknown>;
type Stage = "idle" | "scanning" | "done";

type SelectableParagraph = {
  id: string;
  label: string;
  paragraph_number: number | null;
  page_number: number;
  text: string;
  section_id?: string;
  section_title?: string;
  parent_section_id?: string | null;
  parent_section_title?: string | null;
  is_front_matter?: boolean;
};

type ScanMode = "complete" | "selective";

type ParagraphGroup = {
  id: string;
  section_id: string;
  page_number: number;
  title: string;
  paragraphs: SelectableParagraph[];
};

const ACCEPT = ".pdf,.docx,.txt";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatPercent(value: unknown, isFraction = false): string {
  const percent = isFraction
    ? scoreToPercent(value)
    : percentageValue(value);

  return percent === null ? "—" : `${percent.toFixed(2)}%`;
}

export default function Scan() {
  const [searchParams, setSearchParams] = useSearchParams();
  const savedScanId = searchParams.get("scanId");

  const input = useRef<HTMLInputElement>(null);
  const previewRequestId = useRef(0);

  const [file, setFile] = useState<File | null>(null);
  const [paragraphs, setParagraphs] = useState<SelectableParagraph[]>([]);
  const [selectedParagraphIds, setSelectedParagraphIds] = useState<string[]>([]);
  const [scanMode, setScanMode] = useState<ScanMode>("complete");
  const [isFterDocument, setIsFterDocument] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [title, setTitle] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [scan, setScan] = useState<ScanResponse | null>(null);
  const [result, setResult] = useState<PlagiarismResult | null>(null);
  const [aiResult, setAiResult] = useState<AIAnalysisResponse | null>(null);
  const [sentences, setSentences] = useState<Row[]>([]);
  const [compare, setCompare] = useState<Row[] | null>(null);
  const [comparing, setComparing] = useState(false);
  const [certificate, setCertificate] = useState<CertificateRow | null>(null);
  const [certificateFormOpen, setCertificateFormOpen] = useState(false);
  const [certificateDetails, setCertificateDetails] = useState({
    student_name: "",
    service_number: "",
    course: "",
    batch: "",
  });
  const [busy, setBusy] = useState<string | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);

  const [destinationFolder, setDestinationFolder] = useState("");
  const [documentPages, setDocumentPages] = useState<Row[]>([]);

  const paragraphGroups = paragraphs.reduce<ParagraphGroup[]>(
    (groups, paragraph) => {
      const groupId =
        paragraph.parent_section_id ??
        paragraph.section_id ??
        paragraph.id;

      const groupTitle =
        paragraph.parent_section_title ??
        paragraph.section_title ??
        "Document body";

      const currentGroup = groups[groups.length - 1];

      if (
        currentGroup?.section_id === groupId &&
        currentGroup.page_number === paragraph.page_number
      ) {
        currentGroup.paragraphs.push(paragraph);
      } else {
        groups.push({
          id: paragraph.id,
          section_id: groupId,
          page_number: paragraph.page_number,
          title: groupTitle,
          paragraphs: [paragraph],
        });
      }
      return groups;
    },
    [],
  );

  // Load scan details independently so a failure in one analysis
  // does not prevent the other results from being displayed.
  const loadScanDetails = useCallback(async (scanRecord: ScanResponse) => {
    setScan(scanRecord);
    setTitle(scanRecord.title);

    const scanId = encodeURIComponent(scanRecord.id);

    const [
      plagiarismResult,
      aiAnalysisResult,
      detailResult,
      pageResult,
    ] = await Promise.allSettled([
      apiGet<PlagiarismResult>(`/scans/${scanId}/plagiarism`),
      apiGet<AIAnalysisResponse>(`/scans/${scanId}/ai-results`),
      apiGet<unknown>(`/scans/${scanId}/plagiarism/sentences`),
      apiGet<unknown>(`/scans/${scanId}/pages`),
    ]);

    const warnings: string[] = [];

    if (plagiarismResult.status === "fulfilled") {
      setResult(plagiarismResult.value);
    } else {
      setResult(null);
      warnings.push(
        `Plagiarism results could not be loaded: ${
          plagiarismResult.reason instanceof Error
            ? plagiarismResult.reason.message
            : "unknown error"
        }`,
      );
    }

    if (aiAnalysisResult.status === "fulfilled") {
      setAiResult(aiAnalysisResult.value);

      if (aiAnalysisResult.value.status === "NOT_STARTED") {
        warnings.push("AI analysis has not started for this scan.");
      }
    } else {
      setAiResult(null);
      warnings.push(
        `AI detector results could not be loaded: ${
          aiAnalysisResult.reason instanceof Error
            ? aiAnalysisResult.reason.message
            : "unknown error"
        }`,
      );
    }

    if (detailResult.status === "fulfilled") {
      setSentences(toArray<Row>(detailResult.value));
    } else {
      setSentences([]);
      warnings.push(
        `Match highlighting could not be loaded: ${
          detailResult.reason instanceof Error
            ? detailResult.reason.message
            : "unknown error"
        }`,
      );
    }

    if (pageResult.status === "fulfilled") {
      setDocumentPages(toArray<Row>(pageResult.value));
    } else {
      setDocumentPages([]);
      warnings.push(
        `The extracted document could not be loaded: ${
          pageResult.reason instanceof Error
            ? pageResult.reason.message
            : "unknown error"
        }`,
      );
    }

    setStage("done");

    setNotice(
      warnings.length > 0
        ? warnings.join(" ")
        : "Scan and analysis results loaded successfully.",
    );
  }, []);

  // Restore a previously saved scan using ?scanId=...
  // This hook must remain at the top level of the component.
  useEffect(() => {
    if (!savedScanId) return;

    const requestedScanId = savedScanId;
    let cancelled = false;

    async function loadPreviousScan() {
      setStage("scanning");
      setError(null);
      setNotice(null);

      try {
        const scans = toArray<Row>(await apiGet<unknown>("/scans"));

        const savedScan = scans.find(
          (row) => pickString(row, "id") === requestedScanId,
        );

        if (!savedScan) {
          throw new Error("The requested previous scan could not be found.");
        }

        const scanRecord: ScanResponse = {
          id: requestedScanId,
          title: pickString(savedScan, "title") || "Previous scan",
        };

        if (cancelled) return;

        await loadScanDetails(scanRecord);
      } catch (err) {
        if (!cancelled) {
          setStage("idle");
          setError(
            err instanceof Error
              ? err.message
              : "Could not load previous scan.",
          );
        }
      }
    }

    void loadPreviousScan();

    return () => {
      cancelled = true;
    };
  }, [savedScanId, loadScanDetails]);

  async function previewParagraphs(selected: File) {
    const requestId = ++previewRequestId.current;

    setPreviewing(true);
    setError(null);

    try {
      const form = new FormData();
      form.append("document", selected);

      const preview = await apiUpload<{
        paragraphs: SelectableParagraph[];
        default_selected_ids: string[];
        is_fter: boolean;
      }>("/scans/preview", form);

      if (requestId !== previewRequestId.current) return;

      setParagraphs(preview.paragraphs);

      setSelectedParagraphIds(
        [...new Set(preview.default_selected_ids)].filter((id) =>
          preview.paragraphs.some((paragraph) => paragraph.id === id),
        ),
      );

      setIsFterDocument(preview.is_fter);
    } catch (err) {
      if (requestId !== previewRequestId.current) return;

      setParagraphs([]);
      setSelectedParagraphIds([]);
      setIsFterDocument(false);

      setError(
        err instanceof Error
          ? err.message
          : "Could not identify selectable paragraphs.",
      );
    } finally {
      if (requestId === previewRequestId.current) {
        setPreviewing(false);
      }
    }
  }

  function choose(selected: File | undefined) {
    if (!selected) return;

    const ok = /\.(pdf|docx|txt)$/i.test(selected.name);

    if (!ok) {
      previewRequestId.current += 1;
      setFile(null);
      setParagraphs([]);
      setSelectedParagraphIds([]);
      setPreviewing(false);
      setError("Only PDF, DOCX and TXT files can be scanned.");
      return;
    }

    setError(null);
    setFile(selected);
    setParagraphs([]);
    setSelectedParagraphIds([]);
    setIsFterDocument(false);

    void previewParagraphs(selected);

    if (!title) {
      setTitle(selected.name.replace(/\.[^.]+$/, ""));
    }
  }

  function changeScanMode(mode: ScanMode) {
    setScanMode(mode);

    if (
      mode === "selective" &&
      file &&
      paragraphs.length === 0 &&
      !previewing
    ) {
      setParagraphs([]);
      setSelectedParagraphIds([]);
      setIsFterDocument(false);
      void previewParagraphs(file);
    }
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragOver(false);
    choose(event.dataTransfer.files[0]);
  }

  async function runScan() {
    if (
      !file ||
      stage === "scanning" ||
      (scanMode === "selective" &&
        (previewing || selectedParagraphIds.length === 0))
    ) {
      return;
    }

    setError(null);
    setNotice(null);
    setStage("scanning");
    setCompare(null);
    setCertificate(null);
    setAiResult(null);
    setResult(null);

    try {
      const form = new FormData();

      form.append("document", file);
      form.append("title", title.trim() || file.name);
      form.append("destination_folder", destinationFolder.trim());
      form.append("scan_mode", scanMode);

      if (scanMode === "selective") {
        const availableIds = new Set(
          paragraphs.map((paragraph) => paragraph.id),
        );

        const uniqueSelectedIds = [
          ...new Set(selectedParagraphIds),
        ].filter((id) => availableIds.has(id));

        if (uniqueSelectedIds.length === 0) {
          setStage("idle");
          setError("Select at least one valid paragraph.");
          return;
        }

        form.append(
          "selected_paragraph_ids",
          JSON.stringify(uniqueSelectedIds),
        );
      }

      // The backend starts plagiarism and AI detection automatically.
      // The backend response is returned after both workers finish.
      const created = await apiUpload<ScanResponse>("/scans", form);

      await loadScanDetails(created);
    } catch (err) {
      setStage("idle");
      setError(err instanceof Error ? err.message : "Scan failed");
    }
  }

  function reset() {
    previewRequestId.current += 1;

    setSearchParams({});
    setFile(null);
    setParagraphs([]);
    setSelectedParagraphIds([]);
    setIsFterDocument(false);
    setScanMode("complete");
    setPreviewing(false);
    setTitle("");
    setScan(null);
    setResult(null);
    setAiResult(null);
    setSentences([]);
    setDocumentPages([]);
    setCompare(null);
    setCertificate(null);
    setDestinationFolder("");

    setCertificateDetails({
      student_name: "",
      service_number: "",
      course: "",
      batch: "",
    });

    setStage("idle");
    setError(null);
    setNotice(null);
  }

  async function openCompare() {
    if (!scan) return;

    setComparing(true);
    setError(null);

    try {
      const data = await apiGet<unknown>(
        `/scans/${scan.id}/plagiarism/compare`,
      );

      setCompare(toArray<Row>(data));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not load comparison",
      );
    } finally {
      setComparing(false);
    }
  }

  async function generateCertificate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!scan) return;

    if (!certificateDetails.student_name.trim()) {
      setError("Student officer name is required.");
      return;
    }

    setBusy("certificate");
    setError(null);

    try {
      const created = await apiSend<CertificateRow>(
        "POST",
        `/scans/${scan.id}/certificate`,
        {
          student_name: certificateDetails.student_name.trim(),
          service_number: certificateDetails.service_number.trim() || null,
          course: certificateDetails.course.trim() || null,
          batch: certificateDetails.batch.trim() || null,
        },
      );

      setCertificate(created);
      setCertificateFormOpen(false);

      setNotice(`Certificate ${created.certificate_number} generated.`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not generate certificate",
      );
    } finally {
      setBusy(null);
    }
  }

  async function downloadCertificate() {
    if (!scan) return;

    setBusy("download");

    try {
      await apiDownload(
        `/scans/${scan.id}/certificate/download`,
        `${certificate?.certificate_number ?? "certificate"}.pdf`,
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Download failed",
      );
    } finally {
      setBusy(null);
    }
  }

  // ---------------- upload view ----------------

  if (savedScanId && stage !== "done") {
    return (
      error ? (
        <div className="scan-page scan-loading-page">
          <h1>Previous scan</h1>
          <ErrorBox message={error} />
        </div>
      ) : (
        <ScanProcessingScreen
          title="Opening your previous scan"
          description="We’re retrieving the document and its results."
        />
      )
    );
  }

  if (stage === "scanning") {
    return (
      <ScanProcessingScreen
        title="Your document is being checked"
        description="We’re reviewing the document and preparing your results. Larger files may take a few minutes."
        fileName={file?.name}
        scanMode={scanMode}
      />
    );
  }

  if (stage !== "done") {
    return (
      <div className="scan-page scan-upload-page">
        <header className="scan-upload-header">
          <p className="scan-results-eyebrow">DOCUMENT CHECK</p>
          <h1>Check a document</h1>
          <p>
            Upload a report to review text matches and writing indicators in
            one place.
          </p>
        </header>

        <ErrorBox message={error} />

        <div className="card scan-upload-card">
          <label className="scan-mode-select">
            How much should we check?

            <select
              value={scanMode}
              onChange={(event) =>
                changeScanMode(event.target.value as ScanMode)
              }
            >
              <option value="complete">Complete document</option>
              <option value="selective">Choose sections</option>
            </select>

            <span className="muted">
              {scanMode === "complete"
                ? "Scan all body text. Headings, tables, the table of contents and index entries are excluded."
                : "Choose only the report sections to include in plagiarism detection."}
            </span>
          </label>

          <div className="scan-upload-field">
            <span className="scan-field-label">Your document</span>
            <div
              className={`dropzone${dragOver ? " over" : ""}${file ? " done" : ""}`}
              onDragOver={(event) => {
                event.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => input.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  input.current?.click();
                }
              }}
            >
              {file ? (
                <div className="dropzone-selected">
                  <span className="dropzone-icon" aria-hidden="true">✓</span>
                  <span className="dropzone-file-details">
                    <strong>{file.name}</strong>
                    <span className="muted">
                      {(file.size / 1024).toFixed(0)} KB · Click to choose a
                      different file
                    </span>
                  </span>
                </div>
              ) : (
                <div className="dropzone-prompt">
                  <span className="dropzone-icon" aria-hidden="true">↑</span>
                  <strong>Choose a file or drag it here</strong>
                  <span className="muted">PDF, DOCX or TXT</span>
                </div>
              )}

              <input
                ref={input}
                type="file"
                accept={ACCEPT}
                hidden
                onChange={(event) => choose(event.target.files?.[0])}
              />
            </div>
          </div>

          {isFterDocument && (
            <p style={{ margin: "12px 0 0" }}>
              <span className="fter-badge" role="status">
                FTER format detected
              </span>
            </p>
          )}

          <div className="scan-upload-options">
            <label>
              Document title

              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Report title"
              />
              </label>
          </div>

          {file && scanMode === "selective" && (
            <section
              className="paragraph-selection"
              aria-labelledby="paragraph-selection-title"
            >
              <div className="paragraph-selection-header">
                <div>
                  <h2 id="paragraph-selection-title">
                    {isFterDocument
                      ? "Select FTER sections"
                      : "Select report paragraphs"}
                  </h2>

                  {isFterDocument ? (
                    <p className="muted">
                      Headings and repeated classification headers/footers are
                      excluded. Front matter is available but unselected by
                      default. Summary, every Analysis and Results subparagraph,
                      and Recommendations are selected by default.
                    </p>
                  ) : (
                    <p className="muted">
                      Select the paragraphs to compare. Headings, subheadings,
                      tables, table of contents, and index entries are excluded.
                      Summary and paragraphs 3 and 4 are selected by default
                      when found.
                    </p>
                  )}
                </div>

                <div className="row">
                  <button
                    type="button"
                    className="btn ghost small"
                    onClick={() =>
                      setSelectedParagraphIds(
                        paragraphs.map((item) => item.id),
                      )
                    }
                    disabled={previewing || paragraphs.length === 0}
                  >
                    Select all
                  </button>

                  <button
                    type="button"
                    className="btn ghost small"
                    onClick={() => setSelectedParagraphIds([])}
                    disabled={previewing || paragraphs.length === 0}
                  >
                    Clear
                  </button>
                </div>
              </div>

              {previewing ? (
                <p className="muted">
                  Extracting paragraphs for selection…
                </p>
              ) : paragraphs.length ? (
                <>
                  <div className="muted paragraph-selection-count">
                    {
                      selectedParagraphIds.filter((id) =>
                        paragraphs.some(
                          (paragraph) => paragraph.id === id,
                        ),
                      ).length
                    } of {paragraphs.length} paragraphs selected
                  </div>

                  <div className="paragraph-options">
                    {paragraphGroups.map((group) => {
                      const selectedCount = group.paragraphs.filter(
                        (paragraph) =>
                          selectedParagraphIds.includes(paragraph.id),
                      ).length;

                      const allSelected =
                        selectedCount === group.paragraphs.length &&
                        group.paragraphs.length > 0;

                      return (
                        <div className="paragraph-group" key={group.id}>
                          <label className="paragraph-group-heading">
                            <input
                              type="checkbox"
                              checked={allSelected}
                              ref={(node) => {
                                if (node) {
                                  node.indeterminate =
                                    selectedCount > 0 && !allSelected;
                                }
                              }}
                              onChange={(event) => {
                                setSelectedParagraphIds((current) => {
                                  const groupIds =
                                    group.paragraphs.map(
                                      (item) => item.id,
                                    );

                                  const remaining = current.filter(
                                    (id) => !groupIds.includes(id),
                                  );

                                  return event.target.checked
                                    ? [
                                        ...new Set([
                                          ...remaining,
                                          ...groupIds,
                                        ]),
                                      ]
                                    : remaining;
                                });
                              }}
                            />

                            <strong>{group.title}</strong>
                            <span className="muted">
                              Page {group.page_number}
                            </span>
                          </label>

                          <div className="paragraph-group-items">
                            {group.paragraphs.map((paragraph) => (
                              <label
                                className="paragraph-option"
                                key={paragraph.id}
                              >
                                <input
                                  type="checkbox"
                                  checked={selectedParagraphIds.includes(
                                    paragraph.id,
                                  )}
                                  onChange={(event) => {
                                    setSelectedParagraphIds((current) =>
                                      event.target.checked
                                        ? [
                                            ...new Set([
                                              ...current,
                                              paragraph.id,
                                            ]),
                                          ]
                                        : current.filter(
                                            (id) => id !== paragraph.id,
                                          ),
                                    );
                                  }}
                                />

                                <span>
                                  <strong>{paragraph.label}</strong>

                                  <span className="muted">
                                    Page {paragraph.page_number}
                                  </span>

                                  <span className="paragraph-option-text">
                                    {paragraph.text}
                                  </span>
                                </span>
                              </label>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              ) : error ? null : (
                <p className="muted">
                  Select a document to identify its report sections.
                </p>
              )}
            </section>
          )}

          <details className="scan-advanced-options">
            <summary>More options</summary>
            <label className="scan-storage-field">
              Storage subfolder (optional)

              <input
                value={destinationFolder}
                onChange={(event) =>
                  setDestinationFolder(event.target.value)
                }
                placeholder="e.g. FTER/2026"
              />

              <span className="muted">
                Leave blank to use the default location.
              </span>
            </label>
          </details>

          <div className="scan-upload-footer">
            <span className="muted">
              {file
                ? "Ready to check."
                : "Supports PDF, DOCX and TXT files."}
            </span>
            <button
              type="button"
              className="btn scan-submit-button"
              disabled={
                !file ||
                (scanMode === "selective" &&
                  (previewing ||
                    paragraphs.length === 0 ||
                    selectedParagraphIds.length === 0))
              }
              onClick={() => void runScan()}
            >
              {scanMode === "selective" && previewing
                  ? "Preparing sections…"
                  : scanMode === "selective"
                    ? "Check selected sections"
                    : "Check document"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ---------------- results view ----------------

  const plagiarism = scoreToPercent(result?.overall_similarity);

  const detectorNames: Record<string, string> = {
    CLASSIFIER: "AI-writing estimate (experimental)",
  };
  const semanticsNames: Record<string, string> = {
    AI_LIKELIHOOD_INDICATOR:
      "How strongly this model sees patterns like its training examples; it is not proof of who wrote the document.",
    CORPUS_SIMILARITY:
      "Similarity to text in this system's reference collection.",
    LINGUISTIC_INDICATOR:
      "Writing-style patterns that can appear in both human and AI-written text.",
  };
  const authorshipClassifier =
    aiResult?.detector_results.find(
      (detector) => detector.detector_type === "CLASSIFIER",
    ) ?? null;
  const authorshipScore =
    authorshipClassifier?.status === "COMPLETED"
      ? authorshipClassifier.score
      : null;
  const matchedSentences = result?.statistics?.matched_sentences ?? null;
  const totalSentences = result?.statistics?.total_sentences ?? null;
  const sentenceCoverage = result?.statistics?.sentence_coverage_percentage;
  const aiStatusLabel: Record<string, string> = {
    COMPLETED: "Ready",
    PARTIAL_COMPLETED: "Partly ready",
    PROCESSING: "In progress",
    FAILED: "Could not finish",
    NOT_CONFIGURED: "Not set up",
    NOT_STARTED: "Not started",
    UNAVAILABLE: "Unavailable",
  };

  return (
    <div className="scan-page scan-results-page">
      <header className="scan-results-header">
        <div>
          <p className="scan-results-eyebrow">DOCUMENT CHECK REPORT</p>
          <h1>{scan?.title ?? "Scan result"}</h1>
          <p className="muted">
            A quick guide to text matches and writing indicators found in this
            document.
          </p>
        </div>
        <span
          className={`scan-status-pill ${
            !result
              ? "scan-status-pending"
              : result.status === "COMPLETED"
                ? "scan-status-ready"
                : "scan-status-pending"
          }`}
        >
          {!result
            ? "Results unavailable"
            : result.status === "COMPLETED"
              ? "Scan complete"
              : "Partial results"}
        </span>
      </header>

      <ErrorBox message={error} />

      {notice && <div className="notice">{notice}</div>}

      <div className="gauges">
        <div className="gauge plagiarism-gauge score-tile score-tile-similarity">
          <div className="score-tile-glow" aria-hidden="true" />
          <div className="score-tile-heading">
            <span className="score-tile-icon" aria-hidden="true">
              <ScanSearch size={17} />
            </span>
            <div>
              <div className="lbl">TEXT SIMILARITY</div>
              <div className="score-tile-subtitle">
                Available reference collection
              </div>
            </div>
            <div className="similarity-score-status">
              <span className="score-status-dot" aria-hidden="true" />
              Reference similarity
            </div>
          </div>

          <div
            className={`similarity-score-value ${
              plagiarism === null ? "similarity-score-value-unavailable" : ""
            }`}
          >
            {plagiarism === null ? "Not available" : `${plagiarism.toFixed(2)}%`}
          </div>

          <div
            className="similarity-score-meter"
            role="progressbar"
            aria-label="Text similarity to available references"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={plagiarism ?? undefined}
          >
            <span
              style={{
                width: `${plagiarism === null ? 0 : Math.max(0, Math.min(100, plagiarism))}%`,
              }}
            />
          </div>

          <p className="similarity-score-explanation">
            Estimated share of text resembling available references.
            A match is not a plagiarism decision. Check the highlighted text
            and sources in context.
          </p>
        </div>

        <div className="gauge ai-score-summary score-tile score-tile-ai">
          <div className="score-tile-glow" aria-hidden="true" />
          <div className="score-tile-heading">
            <span className="score-tile-icon" aria-hidden="true">
              <Sparkles size={17} />
            </span>
            <div>
              <div className="lbl">AI-WRITING ESTIMATE</div>
              <div className="score-tile-subtitle">Experimental classifier</div>
            </div>
            <div className="ai-score-summary-status">
              <span
                className={`score-status-dot score-status-dot-${(
                  aiResult?.status ?? "UNAVAILABLE"
                ).toLowerCase()}`}
                aria-hidden="true"
              />
              {aiStatusLabel[aiResult?.status ?? "UNAVAILABLE"] ??
                "Unavailable"}
            </div>
          </div>

          <div
            className={`ai-authorship-value ${
              authorshipScore === null ? "ai-authorship-value-unavailable" : ""
            }`}
          >
            {authorshipScore === null
              ? "Not available"
              : `${authorshipScore.toFixed(2)}%`}
          </div>

          <div
            className="ai-score-meter"
            role="progressbar"
            aria-label="Experimental AI-writing estimate"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={authorshipScore ?? undefined}
          >
            <span
              style={{
                width: `${authorshipScore === null ? 0 : Math.max(0, Math.min(100, authorshipScore))}%`,
              }}
            />
          </div>

          <div className="score-tile-explanation">
            {authorshipScore === null
              ? authorshipClassifier?.status === "NOT_CONFIGURED"
                ? "An AI-writing estimate was not set up for this scan. Similarity matches and writing notes are separate checks."
                : authorshipClassifier?.status === "FAILED"
                  ? "The writing estimate could not be calculated. No score is available."
                  : authorshipClassifier?.status === "PROCESSING" ||
                      aiResult?.status === "PROCESSING"
                    ? "The writing estimate is still being prepared."
                    : "No writing estimate is available for this scan."
              : "Experimental estimate only. It can be wrong and is not proof of who wrote the document."}
          </div>
        </div>
      </div>

      <section className="results-summary-card">
        <div className="results-summary-icon" aria-hidden="true">✓</div>
        <div>
          <h2>In plain language</h2>
          {matchedSentences !== null && totalSentences !== null ? (
            <p>
              We found matches in <strong>{matchedSentences} of {totalSentences}</strong>{" "}
              sentences
              {typeof sentenceCoverage === "number"
                ? ` (${sentenceCoverage.toFixed(1)}% of sentences).`
                : "."}{" "}
              The text similarity score measures how much text resembles
              material in the reference collection; it does not determine
              whether a match is properly cited or constitutes plagiarism.
            </p>
          ) : (
            <p>
              Detailed sentence-matching information is not available. Review
              the results below for the information that could be retrieved.
            </p>
          )}
        </div>
      </section>

      <section className="card analysis-details">
        <h2>Text matches</h2>
        <p className="muted section-intro">
          These counts show where the checker found wording in common with the
          references available to this system.
        </p>

        {!result ? (
          <p className="muted">Text-match details are unavailable.</p>
        ) : (
          <>
            <div className="analysis-metric-grid">
              <Metric
                label="Sentences checked"
                value={result.statistics?.total_sentences ?? "—"}
              />
              <Metric
                label="Sentences with a match"
                value={result.statistics?.matched_sentences ?? "—"}
              />
              <Metric
                label="Share of document text matched"
                value={formatPercent(
                  result.statistics?.text_coverage_percentage,
                )}
              />
            </div>

            <details className="analysis-technical-details">
              <summary>See match categories and more details</summary>
              <div className="analysis-metric-grid">
                <Metric
                  label="Sentences without a match"
                  value={result.statistics?.unmatched_sentences ?? "—"}
                />
                <Metric
                  label="Share of sentences with matches"
                  value={formatPercent(
                    result.statistics?.sentence_coverage_percentage,
                  )}
                />
                <Metric
                  label="Average match strength"
                  value={formatPercent(
                    result.statistics?.average_match_strength,
                    true,
                  )}
                />
                <Metric
                  label="Exact wording"
                  value={result.match_counts?.exact ?? "—"}
                />
                <Metric
                  label="Strongly similar"
                  value={result.match_counts?.high_similarity ?? "—"}
                />
                <Metric
                  label="Somewhat similar"
                  value={result.match_counts?.moderate_similarity ?? "—"}
                />
                <Metric
                  label="Possible related wording"
                  value={result.match_counts?.low_similarity ?? "—"}
                />
              </div>
              <p className="muted">
                Several comparison methods look for exact wording, repeated
                phrase patterns, shared distinctive words, and similar
                meaning. These supporting signals are not separate plagiarism
                percentages and should not be added together.
              </p>
              <div className="analysis-metric-grid">
                {(
                  [
                    ["exact", "Exact wording"],
                    ["ngram", "Phrase patterns"],
                    ["tfidf", "Distinctive words"],
                    ["semantic", "Similar meaning"],
                    ["cross_encoder", "Context comparison"],
                  ] as const
                ).map(([key, label]) => (
                  <Metric
                    key={key}
                    label={label}
                    value={formatPercent(
                      result.algorithm_scores?.[key],
                      true,
                    )}
                  />
                ))}
              </div>
            </details>
          </>
        )}
      </section>

      <section className="card" style={{ marginTop: 20 }}>
        <h2>Writing indicators</h2>

        <p className="muted section-intro">
          These checks provide separate clues. They do not prove who wrote a
          document, and their scores are not combined.
        </p>

        {!aiResult || aiResult.status === "NOT_STARTED" ? (
          <p className="muted">
            No AI analysis results are available for this scan.
          </p>
        ) : (
          <>
            <p>
              <strong>Writing checks:</strong>{" "}
              {aiStatusLabel[aiResult.status] ?? "Status unavailable"}
            </p>

            {aiResult.detector_results.filter(
              (detector) => detector.detector_type === "CLASSIFIER",
            ).length === 0 ? (
              <p className="muted">
                No AI-writing estimate is available for this scan.
              </p>
            ) : (
              <div style={{ display: "grid", gap: 14 }}>
                {aiResult.detector_results
                  .filter((detector) => detector.detector_type === "CLASSIFIER")
                  .map((detector) => {
                  const qwenMetrics = isRecord(detector.metrics)
                    ? detector.metrics
                    : null;
                  const qwenScope = isRecord(qwenMetrics?.scope)
                    ? qwenMetrics.scope
                    : null;
                  const qwenModel =
                    typeof qwenMetrics?.model === "string"
                      ? qwenMetrics.model
                      : detector.model_id;
                  const isDemoCorpus =
                    detector.detector_type === "CORPUS_MATCH" &&
                    qwenMetrics?.development_only === true;
                  const detectorStatus =
                    isDemoCorpus
                      ? "Demo data"
                      : detector.detector_type === "CLASSIFIER" &&
                          detector.status === "COMPLETED"
                        ? "Estimate ready"
                        : aiStatusLabel[detector.status] ??
                          "Status unavailable";

                  return (
                    <div
                      key={detector.id}
                      className="detector-result-card"
                    >
                      <div className="detector-result-heading">
                        <h3>
                          {detectorNames[detector.detector_type] ??
                            detector.detector_type}
                        </h3>
                        <span
                          className={`detector-status ${
                            isDemoCorpus
                              ? "detector-status-demo"
                              : `detector-status-${detector.status.toLowerCase()}`
                          }`}
                        >
                          {detectorStatus}
                        </span>
                      </div>

                      {detector.detector_type === "QWEN_EXPERIMENTAL" ? (
                        <div>
                          <p>
                            This check looks for patterns in the writing and
                            provides observations—not an AI-writing score.
                          </p>
                          <div className="analysis-metric-grid">
                            <Metric
                              label="Notes returned"
                              value={detector.evidence.length}
                            />
                            <Metric
                              label="Sentences reviewed"
                              value={
                                typeof qwenScope?.sentences_analyzed ===
                                "number"
                                  ? qwenScope.sentences_analyzed
                                  : "—"
                              }
                            />
                            <Metric
                              label="Sentences available"
                              value={
                                typeof qwenScope?.sentences_available ===
                                "number"
                                  ? qwenScope.sentences_available
                                  : "—"
                              }
                            />
                            {typeof qwenScope?.sample_truncated ===
                              "boolean" && (
                              <Metric
                                label="Reviewed a sample only?"
                                value={
                                  qwenScope.sample_truncated ? "Yes" : "No"
                                }
                              />
                            )}
                          </div>
                          <p className="muted">
                            These notes are experimental and should be
                            considered alongside the actual writing and
                            supporting evidence.
                          </p>
                        </div>
                      ) : (
                        <>
                          {isDemoCorpus ? (
                            <div className="demo-corpus-notice">
                              <strong>Demo reference data</strong>
                              <p>
                                This compares text with sample documents only.
                                It cannot tell whether a person or AI wrote the
                                document, and it is not evidence or proof of AI
                                authorship.
                              </p>
                              <p>
                                The actual AI-writing estimate is shown
                                separately above when the experimental
                                classifier is available.
                              </p>
                            </div>
                          ) : (
                            <p>
                              <strong>
                                {detector.detector_type === "CLASSIFIER"
                                  ? "Experimental AI-writing estimate:"
                                  : detector.detector_type === "CORPUS_MATCH"
                                    ? "Reference collection similarity:"
                                    : "Writing-style indicator:"}
                              </strong>{" "}
                              {detector.score === null
                                ? "Not available"
                                : `${detector.score.toFixed(2)}%`}
                            </p>
                          )}

                          {!isDemoCorpus && (
                            <p>
                              <strong>What this number means:</strong>{" "}
                              {detector.score_semantics
                                ? semanticsNames[
                                    detector.score_semantics
                                  ] ?? detector.score_semantics
                                : detector.detector_type === "CLASSIFIER"
                                  ? "The model's experimental estimate; it may be incorrect."
                                  : "A comparison signal, not a conclusion about authorship."}
                            </p>
                          )}

                          {detector.detector_type === "CLASSIFIER" && (
                            <p>
                              <strong>Model confidence:</strong>{" "}
                              {detector.confidence === null
                                ? "Not available"
                                : `${(
                                    detector.confidence * 100
                                  ).toFixed(1)}% (not independently verified)`}
                            </p>
                          )}
                        </>
                      )}

                      {detector.explanation && (
                        <p className="muted">
                          {detector.explanation}
                        </p>
                      )}

                      {detector.detector_type === "QWEN_EXPERIMENTAL" && (
                        <div style={{ marginTop: 12 }}>
                          <h4>Writing-pattern observations</h4>

                          {detector.evidence.length === 0 ? (
                            <p className="muted">
                              No sentence-level observations were returned.
                            </p>
                          ) : (
                            <div style={{ display: "grid", gap: 12 }}>
                              {detector.evidence.map((evidence) => (
                                <div
                                  key={evidence.id}
                                  style={{
                                    padding: 12,
                                    border: "1px solid var(--border, #ccc)",
                                    borderRadius: 8,
                                  }}
                                >
                                  <p>
                                    <strong>Category:</strong>{" "}
                                    {evidence.details.category ??
                                      evidence.evidence_type}
                                  </p>

                                  {typeof evidence.details.observation ===
                                    "string" && (
                                    <p>
                                      {evidence.details.observation}
                                    </p>
                                  )}

                                  {typeof evidence.details.quote ===
                                    "string" && (
                                    <blockquote>
                                      <strong>Evidence quote:</strong>
                                      <p>{evidence.details.quote}</p>
                                    </blockquote>
                                  )}

                                  <p className="muted">
                                    <strong>Source sentence:</strong>{" "}
                                    {evidence.sentence_text}
                                  </p>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                      {detector.detector_type === "CLASSIFIER" &&
                        qwenMetrics?.sentence_analysis_status === "FAILED" && (
                          <p className="muted">
                            The overall estimate is available, but sentence
                            highlights could not be generated for this scan.
                          </p>
                        )}

                      <details className="analysis-technical-details compact">
                        <summary>Technical information</summary>
                        {qwenModel && (
                          <p className="muted">
                            Analysis model: {qwenModel}
                          </p>
                        )}
                        <p className="muted">
                          Detector version: {detector.detector_version}
                        </p>
                      </details>
                    </div>
                  );
                  })}
              </div>
            )}
          </>
        )}
      </section>

      <DocumentPreview
        pages={documentPages}
        sentences={sentences}
        aiResult={aiResult}
        selective={scanMode === "selective"}
      />

      {compare && (
        <CompareView
          rows={compare}
          onBack={() => setCompare(null)}
        />
      )}

      <div className="actions">
        <button
          className="btn yellow"
          onClick={() => setSaveOpen(true)}
        >
          Request to save document
        </button>

        <button
          className="btn green"
          disabled={comparing}
          onClick={openCompare}
        >
          {comparing
            ? "Searching for similar contents…"
            : "Compare with references"}
        </button>

        <button
          className="btn"
          disabled={busy === "certificate"}
          onClick={() => {
            setError(null);
            setCertificateFormOpen(true);
          }}
        >
          Generate Certificate
        </button>

        {certificate && (
          <button
            className="btn ghost"
            disabled={busy === "download"}
            onClick={downloadCertificate}
          >
            Download Certificate
          </button>
        )}

        <button className="btn ghost" onClick={reset}>
          Scan another document
        </button>
      </div>

      {saveOpen && file && (
        <SaveRequestModal
          file={file}
          title={scan?.title ?? title}
          onClose={() => setSaveOpen(false)}
          onSent={() => {
            setSaveOpen(false);
            setNotice(
              "Request successfully sent to administrator.",
            );
          }}
        />
      )}

      {certificateFormOpen && (
        <Modal
          title="Certificate information"
          onClose={() => setCertificateFormOpen(false)}
        >
          <p className="muted certificate-form-intro">
            Confirm the details to print on the certificate. Blank service,
            course, or batch fields use the saved profile details when available.
          </p>

          <form
            className="certificate-form"
            onSubmit={generateCertificate}
          >
            <label>
              Student officer name

              <input
                autoFocus
                required
                maxLength={255}
                value={certificateDetails.student_name}
                onChange={(event) =>
                  setCertificateDetails((details) => ({
                    ...details,
                    student_name: event.target.value,
                  }))
                }
                placeholder="Enter the name to print"
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
                placeholder="Optional"
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
                placeholder="Optional"
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
                placeholder="Optional"
              />
            </label>

            {error && <ErrorBox message={error} />}

            <div className="btns">
              <button
                type="button"
                className="btn ghost"
                disabled={busy === "certificate"}
                onClick={() => setCertificateFormOpen(false)}
              >
                Cancel
              </button>

              <button
                type="submit"
                className="btn"
                disabled={busy === "certificate"}
              >
                {busy === "certificate"
                  ? "Generating…"
                  : "Generate certificate"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}

function ScanProcessingScreen({
  title,
  description,
  fileName,
  scanMode,
}: {
  title: string;
  description: string;
  fileName?: string;
  scanMode?: ScanMode;
}) {
  return (
    <main className="scan-page scan-processing-page">
      <section
        className="scan-processing-card"
        role="status"
        aria-live="polite"
        aria-busy="true"
      >
        <div className="scan-loader-visual" aria-hidden="true">
          <span className="scan-loader-orbit scan-loader-orbit-one" />
          <span className="scan-loader-orbit scan-loader-orbit-two" />
          <span className="scan-loader-spark scan-loader-spark-one" />
          <span className="scan-loader-spark scan-loader-spark-two" />
          <div className="scan-loader-document">
            <svg viewBox="0 0 64 72" fill="none">
              <path
                d="M13 4.5h25l14 14V64a4 4 0 0 1-4 4H13a4 4 0 0 1-4-4V8.5a4 4 0 0 1 4-4Z"
                fill="white"
                stroke="currentColor"
                strokeWidth="2"
              />
              <path
                d="M38 5v13h13"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinejoin="round"
              />
              <path
                d="M19 31h24M19 40h24M19 49h17"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
              />
            </svg>
            <span className="scan-loader-beam" />
          </div>
        </div>

        <div className="scan-processing-copy">
          <span className="scan-processing-kicker">
            <span className="scan-processing-live-dot" />
            PROCESSING
          </span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>

        {fileName && (
          <div className="scan-processing-file">
            <span className="scan-processing-file-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path
                  d="M6 3.75h7.5L19 9.25v11H6a2 2 0 0 1-2-2v-12.5a2 2 0 0 1 2-2Z"
                  stroke="currentColor"
                  strokeWidth="1.7"
                  strokeLinejoin="round"
                />
                <path d="M13 4v5.5h5.5" stroke="currentColor" strokeWidth="1.7" />
              </svg>
            </span>
            <span className="scan-processing-file-copy">
              <strong>{fileName}</strong>
              <span>
                {scanMode === "selective"
                  ? "Selected sections"
                  : "Complete document"}
              </span>
            </span>
            <span className="scan-processing-file-check" aria-hidden="true">
              ✓
            </span>
          </div>
        )}

        <div className="scan-processing-progress" aria-hidden="true">
          <span />
        </div>
        <p className="scan-processing-footnote">
          Keep this page open while we finish.
        </p>
      </section>
    </main>
  );
}

function DocumentPreview({
  pages,
  sentences,
  aiResult,
  selective,
}: {
  pages: Row[];
  sentences: Row[];
  aiResult: AIAnalysisResponse | null;
  selective: boolean;
}) {
  type Highlight = {
    start: number;
    end: number;
    matched: boolean;
    aiPattern: boolean;
    score: number | null;
  };

  function findTextRange(
    source: string,
    target: string,
    from: number,
    limit: number,
  ): { start: number; end: number } | null {
    const exactStart = source.indexOf(target, from);

    if (
      exactStart >= from &&
      exactStart + target.length <= limit
    ) {
      return {
        start: exactStart,
        end: exactStart + target.length,
      };
    }

    const words = target.trim().split(/\s+/).filter(Boolean);

    if (words.length === 0) return null;

    const pattern = words
      .map((word) =>
        word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
      )
      .join("\\s+");

    const match = new RegExp(pattern).exec(
      source.slice(from, limit),
    );

    if (!match || match.index === undefined) return null;

    const start = from + match.index;

    return {
      start,
      end: start + match[0].length,
    };
  }

  const pageGroups = new Map<number, Row[]>();
  const aiPatternEvidence = new Map<string, number>();

  for (const detector of aiResult?.detector_results ?? []) {
    if (
      detector.detector_type !== "CLASSIFIER" ||
      detector.status !== "COMPLETED"
    ) {
      continue;
    }

    for (const evidence of detector.evidence) {
      if (evidence.evidence_type === "AI_PATTERN_SENTENCE") {
        aiPatternEvidence.set(
          evidence.sentence_id,
          evidence.evidence_score ?? 0,
        );
      }
    }
  }

  for (const sentence of sentences) {
    const pageNumber = Number(
      sentence.page_number ??
        sentence.scan_page_number ??
        sentence.page ??
        1,
    );

    if (!pageGroups.has(pageNumber)) {
      pageGroups.set(pageNumber, []);
    }

    pageGroups.get(pageNumber)!.push(sentence);
  }

  const previewPages: Row[] = pages;

  if (previewPages.length === 0) {
    return (
      <section className="card doc-view">
        <h2>
          {selective
            ? "Selected content preview"
            : "Complete document preview"}
        </h2>

        <p className="muted">
          {selective
            ? "Selected scan text is unavailable for this scan. Try running the scan again."
            : "Extracted document text is unavailable for this scan. Please try scanning the document again."}
        </p>
      </section>
    );
  }

  return (
    <section className="card doc-view">
      <h2>Review matched text</h2>
      <details className="document-preview-disclosure">
        <summary>
          {selective
            ? "Open original document text and selected-content matches"
            : "Open document text and highlighted matches"}
        </summary>
        <div className="document-highlight-legend" aria-label="Highlight key">
          <span><i className="legend-plagiarism" />Reference-text match</span>
          <span><i className="legend-ai-pattern" />AI-pattern signal</span>
        </div>
        <p className="muted">
          Review the document text as it was extracted, including table rows.
          Reference matches are highlighted yellow; experimental AI-pattern
          signals are underlined. An AI-pattern signal is not proof of authorship.
        </p>
        <div className="document-preview-pages">
          {previewPages.map((page, pageIndex) => {
        const pageNumber = Number(
          page.page_number ?? pageIndex + 1,
        );

        const rawText = String(
          page.raw_text ?? page.text ?? "",
        );

        const candidates = pageGroups.get(pageNumber) ?? [];
        const highlights: Highlight[] = [];

        let cursor = 0;

        for (const sentence of candidates) {
          const sentenceText = String(
            sentence.text ??
              sentence.raw_text ??
              sentence.scan_text ??
              sentence.sentence ??
              "",
          );

          if (!sentenceText) continue;

          let sentenceRange = findTextRange(
            rawText,
            sentenceText,
            cursor,
            rawText.length,
          );

          if (!sentenceRange) {
            sentenceRange = findTextRange(
              rawText,
              sentenceText,
              0,
              rawText.length,
            );
          }

          if (!sentenceRange) continue;

          const { start, end } = sentenceRange;
          cursor = end;
          const sentenceId = String(sentence.id ?? sentence.sentence_id ?? "");
          const aiProbability = aiPatternEvidence.get(sentenceId);

          if (aiProbability !== undefined) {
            highlights.push({
              start,
              end,
              matched: false,
              aiPattern: true,
              score: aiProbability,
            });
          }

          const bestMatch =
            sentence.best_match &&
            typeof sentence.best_match === "object"
              ? (sentence.best_match as Row)
              : {};

          const score = scoreToPercent(
            bestMatch.similarity_score ??
              sentence.similarity_score ??
              sentence.similarity ??
              sentence.score,
          );

          const highlighting =
            sentence.highlighting &&
            typeof sentence.highlighting === "object"
              ? (sentence.highlighting as Row)
              : bestMatch.highlighting &&
                  typeof bestMatch.highlighting === "object"
                ? (bestMatch.highlighting as Row)
                : {};

          const segments = Array.isArray(highlighting.segments)
            ? (highlighting.segments as Row[])
            : [];

          let segmentCursor = start;
          let hasMatchedSegment = false;

          for (const segment of segments) {
            const segmentText = String(
              segment.text ?? segment.raw_text ?? "",
            );

            if (!segmentText) continue;

            const segmentRange = findTextRange(
              rawText,
              segmentText,
              segmentCursor,
              end,
            );

            if (!segmentRange) continue;

            if (
              segment.matched === true &&
              segmentRange.end > segmentRange.start
            ) {
              highlights.push({
                start: segmentRange.start,
                end: segmentRange.end,
                matched: true,
                aiPattern: false,
                score,
              });

              hasMatchedSegment = true;
            }

            segmentCursor = segmentRange.end;
          }

          const flagged =
            sentence.matched === true ||
            sentence.is_plagiarized === true ||
            sentence.is_plagiarised === true ||
            sentence.is_match === true;

          if (flagged && !hasMatchedSegment) {
            highlights.push({
              start,
              end,
              matched: true,
              aiPattern: false,
              score,
            });
          }
        }

        // Merge overlapping or adjacent highlighted ranges.
        highlights.sort((a, b) => a.start - b.start);

        const merged: Highlight[] = [];

        for (const item of highlights) {
          const previous = merged[merged.length - 1];

          if (previous && item.start <= previous.end) {
            previous.end = Math.max(
              previous.end,
              item.end,
            );
            previous.matched ||= item.matched;
            previous.aiPattern ||= item.aiPattern;

            if (
              item.score !== null &&
              (previous.score === null ||
                item.score > previous.score)
            ) {
              previous.score = item.score;
            }
          } else {
            merged.push({ ...item });
          }
        }

        const renderHighlightedRange = (
          rangeStart: number,
          rangeEnd: number,
        ): React.ReactNode[] => {
          const content: React.ReactNode[] = [];
          let position = rangeStart;

          for (const item of merged) {
            const start = Math.max(rangeStart, item.start);
            const end = Math.min(rangeEnd, item.end);
            if (start >= end) continue;

            if (start > position) {
              content.push(
                <span key={`plain-${position}`}>
                  {rawText.slice(position, start).replace(/\\\|/g, "|")}
                </span>,
              );
            }

            content.push(
              <mark
                key={`highlight-${start}`}
                className={[
                  item.matched ? "hl" : "",
                  item.aiPattern ? "hl-ai-pattern" : "",
                  item.matched && item.aiPattern ? "hl-both" : "",
                ].filter(Boolean).join(" ")}
                title={
                  item.matched && item.aiPattern
                    ? "Reference match and experimental AI-pattern signal"
                    : item.aiPattern
                      ? `Experimental AI-pattern signal · ${item.score?.toFixed(1)}% model output`
                      : item.score !== null
                        ? `${item.score}% similar`
                        : "Matched text"
                }
              >
                {rawText.slice(start, end).replace(/\\\|/g, "|")}
              </mark>,
            );
            position = end;
          }

          if (position < rangeEnd) {
            content.push(
              <span key={`plain-${position}`}>
                {rawText.slice(position, rangeEnd).replace(/\\\|/g, "|")}
              </span>,
            );
          }
          return content;
        };

        const lines = rawText.match(/[^\n]*(?:\n|$)/g)?.filter(Boolean) ?? [];
        const content: React.ReactNode[] = [];
        let lineOffset = 0;
        let lineIndex = 0;

        while (lineIndex < lines.length) {
          const line = lines[lineIndex];
          const tableLine = /^\s*\|.*\|\s*(?:\n)?$/.test(line);

          if (!tableLine) {
            const blockStart = lineOffset;
            let blockEnd = lineOffset + line.length;
            lineOffset = blockEnd;
            lineIndex += 1;
            while (
              lineIndex < lines.length &&
              !/^\s*\|.*\|\s*(?:\n)?$/.test(lines[lineIndex])
            ) {
              blockEnd += lines[lineIndex].length;
              lineOffset += lines[lineIndex].length;
              lineIndex += 1;
            }
            content.push(
              <p className="document-text-block" key={`text-${blockStart}`}>
                {renderHighlightedRange(blockStart, blockEnd)}
              </p>,
            );
            continue;
          }

          const tableRows: React.ReactNode[] = [];
          while (
            lineIndex < lines.length &&
            /^\s*\|.*\|\s*(?:\n)?$/.test(lines[lineIndex])
          ) {
            const tableRow = lines[lineIndex];
            const rowStart = lineOffset;
            const delimiters: number[] = [];
            for (let index = 0; index < tableRow.length; index += 1) {
              if (
                tableRow[index] === "|" &&
                (index === 0 || tableRow[index - 1] !== "\\")
              ) {
                delimiters.push(index);
              }
            }
            const cellNodes = delimiters.slice(0, -1).map((delimiter, cellIndex) => {
              const nextDelimiter = delimiters[cellIndex + 1];
              const cellText = tableRow.slice(delimiter + 1, nextDelimiter);
              const leadingWhitespace = cellText.length - cellText.trimStart().length;
              const trailingWhitespace = cellText.length - cellText.trimEnd().length;
              const cellStart = rowStart + delimiter + 1 + leadingWhitespace;
              const cellEnd = Math.max(
                cellStart,
                rowStart + nextDelimiter - trailingWhitespace,
              );
              return (
                <td key={`cell-${cellIndex}`}>
                  {renderHighlightedRange(cellStart, cellEnd)}
                </td>
              );
            });
            tableRows.push(
              <tr key={`row-${rowStart}`}>{cellNodes}</tr>,
            );
            lineOffset += tableRow.length;
            lineIndex += 1;
          }
          content.push(
            <div className="document-table-wrap" key={`table-${lineOffset}`}>
              <table className="document-content-table">
                <tbody>{tableRows}</tbody>
              </table>
            </div>,
          );
        }

        return (
          <article
            key={pageNumber}
            className="document-page"
            style={{
              marginBottom: 20,
              padding: 20,
              border: "1px solid var(--border, #ddd)",
              borderRadius: 8,
              background: "var(--card, #fff)",
              color: "var(--text, #222)",
            }}
          >
            <h3
              style={{
                marginTop: 0,
                paddingBottom: 10,
                borderBottom:
                  "1px solid var(--border, #ddd)",
              }}
            >
              Page {pageNumber}
            </h3>

            <div
              className="document-page-content"
              style={{
                overflowWrap: "anywhere",
                lineHeight: 1.8,
                fontFamily: "Arial",
              }}
            >
              {content.length > 0 ? content : rawText}
            </div>
          </article>
        );
          })}
        </div>
      </details>
    </section>
  );
}

function CompareView({
  rows,
  onBack,
}: {
  rows: Row[];
  onBack: () => void;
}) {
  return (
    <>
      <button
        className="btn ghost small"
        style={{ marginBottom: 10 }}
        onClick={onBack}
      >
        ← Back
      </button>

      {rows.length === 0 ? (
        <div className="card muted">
          No similar content was found.
        </div>
      ) : (
        <div className="compare">
          <div className="pane">
            <strong>Your document</strong>

            {rows.map((row, index) => (
              <div className="pair" key={index}>
                {(
                  pickString(row, "section_title") ||
                  pickString(row, "paragraph_title")
                ) && (
                  <div className="muted">
                    {pickString(row, "section_title")}

                    {pickString(row, "section_title") &&
                      pickString(row, "paragraph_title") &&
                      " · "}

                    {pickString(row, "paragraph_title")}
                  </div>
                )}

                <div className="muted">
                  Page{" "}
                  {pickString(
                    row,
                    "scan_page_number",
                    "page_number",
                  ) || "—"}
                </div>

                <mark className="hl">
                  {pickString(row, "scan_text", "text")}
                </mark>
              </div>
            ))}
          </div>

          <div className="pane">
            <strong>Matching source</strong>

            {rows.map((row, index) => (
              <div className="pair" key={index}>
                <div className="muted">
                  {pickString(
                    row,
                    "reference_file_name",
                    "file_name",
                    "reference_title",
                    "reference_document_title",
                    "title",
                  ) || "Reference"}

                  {pickString(
                    row,
                    "reference_title",
                    "reference_document_title",
                  ) &&
                    pickString(
                      row,
                      "reference_title",
                      "reference_document_title",
                    ) !==
                      pickString(
                        row,
                        "reference_file_name",
                        "file_name",
                      ) &&
                    ` (${pickString(
                      row,
                      "reference_title",
                      "reference_document_title",
                    )})`}

                  {" · page "}
                  {pickString(row, "reference_page_number") || "—"}

                  {scoreToPercent(row.similarity_score) !== null &&
                    ` · ${scoreToPercent(
                      row.similarity_score,
                    )}%`}
                </div>

                <mark className="hl">
                  {pickString(row, "reference_text")}
                </mark>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div className="analysis-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SaveRequestModal({
  file,
  title,
  onClose,
  onSent,
}: {
  file: File;
  title: string;
  onClose: () => void;
  onSent: () => void;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setBusy(true);
    setError(null);

    try {
      const form = new FormData();

      form.append("document", file);
      form.append("title", title);
      form.append("reason", reason);

      await apiUpload(
        "/reference/requests/add",
        form,
      );

      onSent();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Request failed",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Request to save in database"
      onClose={onClose}
    >
      <form onSubmit={submit}>
        <ErrorBox message={error} />

        <div className="muted">
          Sends “{title}” to the administrator for approval.
        </div>

        <label>
          Reason

          <textarea
            rows={3}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>

        <div className="btns">
          <button
            type="button"
            className="btn ghost"
            onClick={onClose}
          >
            Cancel
          </button>

          <button
            className="btn"
            disabled={busy}
          >
            {busy ? "Sending…" : "Send request"}
          </button>
        </div>
      </form>
    </Modal>
  );
}