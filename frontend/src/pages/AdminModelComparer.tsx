import { useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDownToLine,
  Cpu,
  FileUp,
  Gauge,
  Info,
  Play,
  Plus,
  RefreshCw,
  Server,
  Trash2,
} from "lucide-react";
import { apiGet, apiSend } from "../api/client";

type ModelInfo = {
  name: string;
  available: boolean;
  mteb: MtebInfo;
};

type MtebInfo = {
  benchmark: string;
  overall_task_score: number;
  categories: Record<string, number | null>;
};

type BenchmarkCase = {
  text_a: string;
  text_b: string;
  similar: boolean;
};

type CaseScore = BenchmarkCase & { similarity: number };

type ModelResult = {
  name: string;
  checkpoint_size_bytes: number;
  parameter_count: number;
  parameter_memory_bytes: number;
  inference_dtype: string;
  embedding_dimension: number;
  max_sequence_length: number;
  architecture: string;
  pooling: string;
  load_seconds: number;
  benchmark_repetitions: number;
  unique_text_count: number;
  median_batch_seconds: number;
  p95_batch_seconds: number;
  batch_latency_stddev_seconds: number;
  median_ms_per_text: number;
  texts_per_second: number;
  pair_scores_per_second: number;
  mean_embedding_norm: number;
  min_embedding_norm: number;
  max_embedding_norm: number;
  truncated_text_count: number;
  truncated_text_percent: number;
  mean_input_tokens: number;
  p95_input_tokens: number;
  max_input_tokens: number;
  quality: {
    roc_auc: number;
    accuracy_at_0_5: number;
    precision_at_0_5: number;
    recall_at_0_5: number;
    f1_at_0_5: number;
    best_threshold: number;
    best_f1: number;
    positive_mean_similarity: number;
    negative_mean_similarity: number;
    similarity_margin: number;
    confusion_at_0_5: {
      true_positive: number;
      false_positive: number;
      true_negative: number;
      false_negative: number;
    };
  };
  case_scores: CaseScore[];
};

type ComparisonReport = {
  generated_at: string;
  device: string;
  case_count: number;
  positive_case_count: number;
  negative_case_count: number;
  mteb_results: Record<string, MtebInfo>;
  results: ModelResult[];
};

type CsvParser = {
  rows: string[][];
  error: string | null;
};

const initialCases: BenchmarkCase[] = [
  {
    text_a: "The aircraft was inspected before the scheduled maintenance.",
    text_b: "Before scheduled maintenance, technicians inspected the aircraft.",
    similar: true,
  },
  {
    text_a: "The crew must complete the checklist before engine startup.",
    text_b: "Before starting the engine, the crew is required to finish the checklist.",
    similar: true,
  },
  {
    text_a: "All inspection findings must be recorded in the maintenance log.",
    text_b: "Every result from the inspection should be entered into the aircraft service record.",
    similar: true,
  },
  {
    text_a: "The report must include the measured temperature and pressure.",
    text_b: "Record both pressure and temperature readings in the report.",
    similar: true,
  },
  {
    text_a: "The aircraft was inspected before the scheduled maintenance.",
    text_b: "The weather forecast predicts rain across the northern region.",
    similar: false,
  },
  {
    text_a: "The crew must complete the checklist before engine startup.",
    text_b: "A database index can improve the speed of a search query.",
    similar: false,
  },
  {
    text_a: "All inspection findings must be recorded in the maintenance log.",
    text_b: "The classroom was repainted during the winter holiday.",
    similar: false,
  },
  {
    text_a: "The report must include the measured temperature and pressure.",
    text_b: "A new library opened near the city centre last month.",
    similar: false,
  },
];

function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit > 1 ? 2 : 1)} ${units[unit]}`;
}

function formatNumber(value: number | null | undefined): string {
  return value == null ? "—" : value.toLocaleString("en-IN");
}

const MTEB_CATEGORY_LABELS: Record<string, string> = {
  bitext_mining: "Bitext mining",
  classification: "Classification",
  clustering: "Clustering",
  pair_classification: "Pair classification",
  reranking: "Reranking",
  retrieval: "Retrieval",
  sts: "Semantic similarity",
  summarization: "Summarization",
};

function parseCsv(content: string): CsvParser {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  const input = content.replace(/^\uFEFF/, "");

  for (let index = 0; index < input.length; index += 1) {
    const character = input[index];
    if (quoted) {
      if (character === '"' && input[index + 1] === '"') {
        cell += '"';
        index += 1;
      } else if (character === '"') {
        quoted = false;
      } else {
        cell += character;
      }
    } else if (character === '"' && cell.length === 0) {
      quoted = true;
    } else if (character === ",") {
      row.push(cell.trim());
      cell = "";
    } else if (character === "\n" || character === "\r") {
      if (character === "\r" && input[index + 1] === "\n") index += 1;
      row.push(cell.trim());
      if (row.some((value) => value.length > 0)) rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += character;
    }
  }

  if (quoted) return { rows: [], error: "The CSV contains an unclosed quote." };
  row.push(cell.trim());
  if (row.some((value) => value.length > 0)) rows.push(row);
  return { rows, error: null };
}

function parseLabel(value: string): boolean | null {
  const normalized = value.trim().toLowerCase();
  if (["1", "true", "yes", "similar", "positive"].includes(normalized)) {
    return true;
  }
  if (["0", "false", "no", "dissimilar", "negative"].includes(normalized)) {
    return false;
  }
  return null;
}

function parseBenchmarkCsv(content: string): BenchmarkCase[] {
  const parsed = parseCsv(content);
  if (parsed.error) throw new Error(parsed.error);
  if (parsed.rows.length < 2) {
    throw new Error("The CSV must contain a header and at least one data row.");
  }

  const headers = parsed.rows[0].map((header) => header.toLowerCase());
  const textAIndex = headers.indexOf("text_a");
  const textBIndex = headers.indexOf("text_b");
  const labelIndex = headers.indexOf("label");
  if (textAIndex < 0 || textBIndex < 0 || labelIndex < 0) {
    throw new Error("CSV columns must include text_a, text_b, and label.");
  }

  const cases = parsed.rows.slice(1).map((values, index) => {
    const textA = values[textAIndex]?.trim() ?? "";
    const textB = values[textBIndex]?.trim() ?? "";
    const label = parseLabel(values[labelIndex] ?? "");
    if (!textA || !textB || label == null) {
      throw new Error(
        `CSV row ${index + 2} needs two texts and a label (1/0 or similar/dissimilar).`,
      );
    }
    if (textA.length > 12_000 || textB.length > 12_000) {
      throw new Error(`CSV row ${index + 2} exceeds the 12,000 character limit.`);
    }
    return { text_a: textA, text_b: textB, similar: label };
  });

  if (cases.length > 200) {
    throw new Error("The benchmark is limited to 200 text pairs.");
  }
  return cases;
}

function MetricRow({
  label,
  values,
  modelCount,
}: {
  label: string;
  values: string[];
  modelCount: number;
}) {
  return (
    <div
      className="grid items-center gap-3 border-b border-slate-100 py-3 last:border-b-0"
      style={{
        gridTemplateColumns: `minmax(14rem, 1fr) repeat(${modelCount}, minmax(9rem, max-content))`,
      }}
    >
      <span className="text-xs text-slate-600">{label}</span>
      {values.map((value, index) => (
        <span key={index} className="text-right text-xs font-semibold tabular-nums text-slate-800">{value}</span>
      ))}
    </div>
  );
}

export default function AdminModelComparer() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [cases, setCases] = useState<BenchmarkCase[]>(initialCases);
  const [repetitions, setRepetitions] = useState(3);
  const [report, setReport] = useState<ComparisonReport | null>(null);
  const [loadingModels, setLoadingModels] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  async function loadModels() {
    setLoadingModels(true);
    setError("");
    try {
      setModels(await apiGet<ModelInfo[]>("/admin/model-comparer/models"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load model details.");
    } finally {
      setLoadingModels(false);
    }
  }

  useEffect(() => {
    void loadModels();
  }, []);

  const updateCase = (
    index: number,
    key: keyof BenchmarkCase,
    value: string | boolean,
  ) => {
    setCases((current) =>
      current.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [key]: value } : item,
      ),
    );
  };

  async function importCsv(file: File | undefined) {
    if (!file) return;
    setError("");
    try {
      if (file.size > 2_000_000) {
        throw new Error("CSV files must be 2 MB or smaller.");
      }
      const content = await file.text();
      const importedCases = parseBenchmarkCsv(content);
      if (importedCases.length < 4) {
        throw new Error("Import at least four pairs for a useful comparison.");
      }
      setCases(importedCases);
      setReport(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read that CSV file.");
    } finally {
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function runComparison() {
    setError("");
    const positiveCount = cases.filter((item) => item.similar).length;
    const negativeCount = cases.length - positiveCount;
    if (cases.length < 4 || positiveCount < 2 || negativeCount < 2) {
      setError("Add at least two similar and two dissimilar text pairs.");
      return;
    }
    if (cases.some((item) => !item.text_a.trim() || !item.text_b.trim())) {
      setError("Every test pair must contain both texts.");
      return;
    }
    if (models.length < 2 || models.some((model) => !model.available)) {
      setError("All listed local models must be present before the comparison can run.");
      return;
    }

    setRunning(true);
    setReport(null);
    try {
      const result = await apiSend<ComparisonReport>(
        "POST",
        "/admin/model-comparer/run",
        { cases, repetitions },
      );
      setReport(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The model comparison failed.");
    } finally {
      setRunning(false);
    }
  }

  function downloadReport() {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `model-comparison-${report.generated_at.slice(0, 10)}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  const results = report?.results ?? [];
  const comparisonMetrics = report
    ? [
        {
          label: "ROC AUC · ranking quality",
          values: results.map((result) => result.quality.roc_auc.toFixed(3)),
        },
        {
          label: "F1 · fixed cosine threshold 0.50",
          values: results.map((result) => result.quality.f1_at_0_5.toFixed(3)),
        },
        {
          label: "F1 · best threshold on this dataset",
          values: results.map((result) => `${result.quality.best_f1.toFixed(3)} @ ${result.quality.best_threshold.toFixed(3)}`),
        },
        {
          label: "Accuracy · threshold 0.50",
          values: results.map((result) => `${(result.quality.accuracy_at_0_5 * 100).toFixed(1)}%`),
        },
        {
          label: "Precision / recall · threshold 0.50",
          values: results.map((result) => `${result.quality.precision_at_0_5.toFixed(3)} / ${result.quality.recall_at_0_5.toFixed(3)}`),
        },
        {
          label: "Positive − negative mean similarity",
          values: results.map((result) => result.quality.similarity_margin.toFixed(3)),
        },
        {
          label: "Cold model load",
          values: results.map((result) => `${result.load_seconds.toFixed(2)} s`),
        },
        {
          label: "Median encode latency / unique text",
          values: results.map((result) => `${result.median_ms_per_text.toFixed(2)} ms`),
        },
        {
          label: "P95 batch latency · all unique texts",
          values: results.map((result) => `${result.p95_batch_seconds.toFixed(3)} s`),
        },
        {
          label: "Batch latency variation · standard deviation",
          values: results.map((result) => `${result.batch_latency_stddev_seconds.toFixed(3)} s`),
        },
        {
          label: "Encode throughput",
          values: results.map((result) => `${result.texts_per_second.toFixed(1)} texts/s`),
        },
        {
          label: "Parameters",
          values: results.map((result) => formatNumber(result.parameter_count)),
        },
        {
          label: "MTEB Mean(Task) · suite varies by model",
          values: results.map((result) => {
            const mteb = report.mteb_results[result.name];
            return `${mteb.overall_task_score.toFixed(2)} · ${mteb.benchmark}`;
          }),
        },
        {
          label: "Parameter memory · actual inference dtype",
          values: results.map((result) => `${formatBytes(result.parameter_memory_bytes)} · ${result.inference_dtype}`),
        },
        {
          label: "Checkpoint / embedding dimensions",
          values: results.map((result) => `${formatBytes(result.checkpoint_size_bytes)} / ${result.embedding_dimension}`),
        },
        {
          label: "Input token lengths · mean / P95 / max",
          values: results.map((result) => `${result.mean_input_tokens.toFixed(0)} / ${result.p95_input_tokens.toFixed(0)} / ${result.max_input_tokens}`),
        },
        {
          label: "Truncated texts at model max length",
          values: results.map((result) => `${result.truncated_text_count} (${result.truncated_text_percent.toFixed(1)}%)`),
        },
        {
          label: "Embedding norm · min / mean / max",
          values: results.map((result) => `${result.min_embedding_norm.toFixed(3)} / ${result.mean_embedding_norm.toFixed(3)} / ${result.max_embedding_norm.toFixed(3)}`),
        },
      ]
    : [];

  return (
    <div className="admin-model-comparer mx-auto max-w-7xl space-y-7">
      <section className="overflow-hidden rounded-3xl bg-gradient-to-br from-[#0d1d36] via-[#12345b] to-[#175c91] px-6 py-7 text-white shadow-lg md:px-9 md:py-9">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-sky-300/20 bg-sky-200/10 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-sky-200">
              <Activity size={13} />
              Offline embedding evaluation
            </div>
            <h1 className="mt-4 text-2xl font-bold tracking-tight md:text-3xl">
              Model comparer
            </h1>
            <p className="mt-2 text-sm leading-6 text-blue-100/80">
              Evaluate all available local embedding models on the same labeled
              text pairs. Compare quality, operating speed, model footprint, and
              sequence handling without sending text outside this server.
            </p>
          </div>
          <div className="rounded-2xl border border-white/15 bg-white/[0.07] p-4">
            <div className="flex items-center gap-2 text-xs text-blue-100">
              <Server size={15} /> Evaluation device
            </div>
            <p className="mt-2 text-lg font-bold">CPU · local models</p>
            <p className="mt-1 text-[11px] text-blue-100/70">Sequential, single-model runs</p>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-slate-900">Models under test</h2>
            <p className="mt-1 text-xs text-slate-500">
              Model configuration is read from the local checkpoint files.
            </p>
          </div>
          <button
            onClick={() => void loadModels()}
            disabled={loadingModels}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            <RefreshCw size={14} className={loadingModels ? "animate-spin" : ""} />
            Refresh model details
          </button>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          {models.map((model) => (
            <article key={model.name} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
                <h3 className="min-w-0 break-words text-sm font-bold text-slate-900">{model.name}</h3>
                <div className="shrink-0 rounded-lg bg-blue-50 px-3 py-2 text-right">
                  <span className="text-[10px] font-bold uppercase tracking-wide text-blue-800">Overall MTEB</span>
                  <p className="mt-0.5 text-xl font-bold tabular-nums leading-tight text-slate-900">
                    {model.mteb.overall_task_score.toFixed(2)}
                  </p>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                {Object.entries(MTEB_CATEGORY_LABELS).map(([category, label]) => {
                  const score = model.mteb.categories[category];
                  return (
                    <div key={category} className="min-w-0 rounded-lg bg-slate-50 px-2.5 py-2">
                      <span className="block min-h-8 text-[10px] leading-4 text-slate-500">{label}</span>
                      <span className="mt-1 block text-sm font-semibold tabular-nums text-slate-800">
                        {score == null ? "—" : score.toFixed(2)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </article>
          ))}
          {loadingModels && models.length === 0 && (
            <p className="text-sm text-slate-500">Reading local model configurations…</p>
          )}
        </div>
      </section>

      <section className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-950">
        <Info size={16} className="mt-0.5 shrink-0" />
        <div>
          <p className="font-bold">Why the overall MTEB score has limits</p>
          <p className="mt-1">
            MTEB measures different skills across bitext mining, classification,
            clustering, pair classification, reranking, retrieval, semantic
            similarity, and summarization. Mean(Task) gives each benchmark task
            equal weight, so its result can shift with the benchmark version,
            task mix, language, and evaluation protocol.             The published
            figures use different benchmark task sets; do not treat their
            difference as a head-to-head win. Use the same MTEB release and
            settings for a fair comparison, and use a representative held-out
            dataset to choose a model for this application.
          </p>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-slate-900">Labeled benchmark pairs</h2>
            <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">
              “Similar” means the pair should be recognized as semantically
              related; “dissimilar” means unrelated. Starter examples are a
              smoke test, not a representative or statistically rigorous
              benchmark. Import your domain-labeled CSV for reliable decisions.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <input
              ref={fileInput}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(event) => void importCsv(event.target.files?.[0])}
            />
            <button
              onClick={() => fileInput.current?.click()}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              <FileUp size={14} /> Import labeled CSV
            </button>
            <button
              onClick={() => {
                setCases((current) => [
                  ...current,
                  { text_a: "", text_b: "", similar: true },
                ]);
                setReport(null);
              }}
              disabled={cases.length >= 200}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              <Plus size={14} /> Add pair
            </button>
          </div>
        </div>
        <div className="mt-4 overflow-x-auto">
          <div className="min-w-[760px] space-y-3">
            {cases.map((item, index) => (
              <div key={index} className="grid grid-cols-[2rem_minmax(0,1fr)_minmax(0,1fr)_9rem_2rem] items-start gap-2">
                <span className="pt-3 text-xs font-semibold text-slate-400">{index + 1}</span>
                <textarea
                  aria-label={`Pair ${index + 1} first text`}
                  maxLength={12_000}
                  rows={2}
                  value={item.text_a}
                  onChange={(event) => updateCase(index, "text_a", event.target.value)}
                  className="resize-y rounded-lg border border-slate-200 px-3 py-2 text-xs leading-5 text-slate-700 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/10"
                  placeholder="First text"
                />
                <textarea
                  aria-label={`Pair ${index + 1} second text`}
                  maxLength={12_000}
                  rows={2}
                  value={item.text_b}
                  onChange={(event) => updateCase(index, "text_b", event.target.value)}
                  className="resize-y rounded-lg border border-slate-200 px-3 py-2 text-xs leading-5 text-slate-700 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/10"
                  placeholder="Second text"
                />
                <select
                  aria-label={`Pair ${index + 1} label`}
                  value={item.similar ? "similar" : "dissimilar"}
                  onChange={(event) => updateCase(index, "similar", event.target.value === "similar")}
                  className="rounded-lg border border-slate-200 bg-white px-2 py-2.5 text-xs text-slate-700 outline-none focus:border-blue-400"
                >
                  <option value="similar">Similar</option>
                  <option value="dissimilar">Dissimilar</option>
                </select>
                <button
                  aria-label={`Remove pair ${index + 1}`}
                  onClick={() => {
                    setCases((current) => current.filter((_, i) => i !== index));
                    setReport(null);
                  }}
                  className="rounded-lg p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-4 border-t border-slate-100 pt-4">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
            <span>{cases.length} pairs</span>
            <span>{cases.filter((item) => item.similar).length} similar</span>
            <span>{cases.filter((item) => !item.similar).length} dissimilar</span>
            <label className="inline-flex items-center gap-2">
              Repetitions
              <select
                value={repetitions}
                onChange={(event) => setRepetitions(Number(event.target.value))}
                className="rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
              >
                {[1, 3, 5, 10].map((value) => <option key={value} value={value}>{value}×</option>)}
              </select>
            </label>
          </div>
          <button
            onClick={() => void runComparison()}
            disabled={running || loadingModels || models.length < 2}
            className="inline-flex items-center gap-2 rounded-xl bg-[#12345b] px-4 py-2.5 text-xs font-bold text-white shadow-sm hover:bg-[#194a7b] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? <RefreshCw size={15} className="animate-spin" /> : <Play size={15} />}
            {running ? "Comparing models…" : "Run thorough comparison"}
          </button>
        </div>
      </section>

      {error && (
        <div role="alert" className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          <AlertTriangle size={18} className="mt-0.5 shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {running && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
          <div className="flex items-center gap-2 font-semibold"><Cpu size={17} /> Running all models sequentially</div>
          <p className="mt-1 text-xs leading-5 text-blue-800">
            Each checkpoint is loaded from disk, warmed up, and benchmarked
            repeatedly on CPU. This can take a few minutes; keep this page open.
          </p>
        </div>
      )}

      {report && results.length > 0 && (
        <>
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-slate-900">Comparison results</h2>
                <p className="mt-1 text-xs text-slate-500">
                  {report.case_count} labeled pairs · {report.positive_case_count} similar · {report.negative_case_count} dissimilar · {report.device} · {new Date(report.generated_at).toLocaleString()}
                </p>
              </div>
              <button
                onClick={downloadReport}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                <ArrowDownToLine size={14} /> Download full JSON
              </button>
            </div>
            <div className="overflow-x-auto">
              <div className="min-w-max">
                <div
                  className="mb-2 grid gap-3 text-[10px] font-bold uppercase tracking-wide text-slate-400"
                  style={{
                    gridTemplateColumns: `minmax(14rem, 1fr) repeat(${results.length}, minmax(9rem, max-content))`,
                  }}
                >
                  <span>Metric</span>
                  {results.map((result) => <span key={result.name} className="text-right">{result.name}</span>)}
                </div>
                {comparisonMetrics.map((metric) => (
                  <MetricRow
                    key={metric.label}
                    label={metric.label}
                    values={metric.values}
                    modelCount={results.length}
                  />
                ))}
              </div>
            </div>
            <p className="mt-4 flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-[11px] leading-5 text-amber-900">
              <Info size={15} className="mt-0.5 shrink-0" />
              The best-F1 threshold is selected and scored on the same dataset,
              so it is optimistic and is not a production threshold. Use a
              separate validation set to calibrate thresholds and a held-out
              test set to estimate generalization.
            </p>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6">
            <div className="mb-4 flex items-center gap-2">
              <Gauge size={17} className="text-blue-700" />
              <h2 className="text-base font-bold text-slate-900">Pair-by-pair cosine scores</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px] text-left text-xs">
                <thead className="border-b border-slate-200 text-[10px] uppercase tracking-wide text-slate-400">
                  <tr>
                    <th className="pb-3 pr-3">Expected</th>
                    {results.map((result) => <th key={result.name} className="pb-3 pr-3">{result.name}</th>)}
                    <th className="pb-3">First text</th>
                  </tr>
                </thead>
                <tbody>
                  {results[0].case_scores.map((item, index) => {
                    return (
                      <tr key={index} className="border-b border-slate-100 last:border-0">
                        <td className="py-3 pr-3">
                          <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${item.similar ? "bg-blue-50 text-blue-700" : "bg-slate-100 text-slate-600"}`}>
                            {item.similar ? "Similar" : "Dissimilar"}
                          </span>
                        </td>
                        {results.map((result) => {
                          const score = result.case_scores[index];
                          const correct = (score.similarity >= 0.5) === item.similar;
                          return (
                            <td key={result.name} className={`py-3 pr-3 font-mono ${correct ? "text-emerald-700" : "text-rose-700"}`}>{score.similarity.toFixed(4)}</td>
                          );
                        })}
                        <td className="max-w-lg truncate py-3 text-slate-600" title={item.text_a}>{item.text_a}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-[11px] text-slate-500">
              Green/red is correctness at cosine 0.50 only. Similarity scales
              and suitable thresholds can differ substantially by model.
            </p>
          </section>
        </>
      )}

      <section className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs leading-5 text-slate-600">
        <Info size={16} className="mt-0.5 shrink-0 text-slate-500" />
        <p>
          CSV format: <code className="rounded bg-white px-1.5 py-0.5">text_a,text_b,label</code>.
          Labels may be 1/0, true/false, yes/no, or similar/dissimilar. Use
          representative, adjudicated examples and a held-out set. Comparisons
          run locally on CPU, one model at a time; supplied text is processed
          in memory and is not saved by this feature.
        </p>
      </section>
    </div>
  );
}
