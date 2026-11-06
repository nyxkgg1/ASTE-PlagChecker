import { useEffect, useState, type FormEvent } from "react";
import { apiGet, apiSend } from "../api/client";
import { ErrorBox } from "../components/ui";

type PlagiarismModel = {
  name: string;
  embedding_dimension: number;
};

type PlagiarismModelSettings = {
  models: PlagiarismModel[];
  selected_model: string;
};

type UpdatedPlagiarismModelSettings = {
  selected_model: string;
  reindexed_sentences: number;
};

export default function AdminPlagiarismModel() {
  const [models, setModels] = useState<PlagiarismModel[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [savedModel, setSavedModel] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadSettings() {
      setLoading(true);
      setError(null);
      try {
        const settings = await apiGet<PlagiarismModelSettings>(
          "/admin/plagiarism-model",
        );
        if (cancelled) return;
        setModels(settings.models);
        setSelectedModel(settings.selected_model);
        setSavedModel(settings.selected_model);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Could not load plagiarism model settings.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void loadSettings();
    return () => {
      cancelled = true;
    };
  }, []);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await apiSend<UpdatedPlagiarismModelSettings>(
        "PUT",
        "/admin/plagiarism-model",
        { model_name: selectedModel },
      );
      setSelectedModel(updated.selected_model);
      setSavedModel(updated.selected_model);
      setNotice(
        `Plagiarism model updated. ${updated.reindexed_sentences} reference sentences indexed.`,
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not update the plagiarism model.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <h1>Plagiarism Model</h1>
      <p className="muted">
        Select the local sentence-embedding model used to compare documents
        against the reference database. Compatible models in the models folder
        are detected automatically.
      </p>
      <ErrorBox message={error} />
      {notice && <div className="notice">{notice}</div>}
      <form className="card exclusion-settings" onSubmit={save}>
        <label>
          Model for plagiarism detection
          <select
            value={selectedModel}
            onChange={(event) => setSelectedModel(event.target.value)}
            disabled={loading || saving || models.length === 0}
          >
            {selectedModel &&
              !models.some((model) => model.name === selectedModel) && (
                <option value={selectedModel} disabled>
                  {selectedModel} (unavailable; choose another model)
                </option>
              )}
            {models.map((model) => (
              <option key={model.name} value={model.name}>
                {model.name} ({model.embedding_dimension} dimensions)
              </option>
            ))}
          </select>
        </label>
        {models.length === 0 && !loading && (
          <p className="muted">
            No compatible local embedding models were found in the models
            folder.
          </p>
        )}
        <p className="muted">
          Changing the model generates embeddings for the existing reference
          database and may take some time. Only compatible local embedding
          models with dimensions supported by the database are listed.
        </p>
        <div className="row">
          <button
            className="btn"
            type="submit"
            disabled={
              loading ||
              saving ||
              !selectedModel ||
              selectedModel === savedModel
            }
          >
            {loading ? "Loading…" : saving ? "Updating model…" : "Save model"}
          </button>
        </div>
      </form>
    </>
  );
}
