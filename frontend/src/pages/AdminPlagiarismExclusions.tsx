import { useEffect, useState, type FormEvent } from "react";
import { apiGet, apiSend } from "../api/client";
import { ErrorBox } from "../components/ui";

type Exclusions = {
  words: string[];
  phrases: string[];
};

function asLines(values: string[]): string {
  return values.join("\n");
}

function parseLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((entry) => entry.trim())
    .filter(Boolean);
}

export default function AdminPlagiarismExclusions() {
  const [words, setWords] = useState("");
  const [phrases, setPhrases] = useState("");
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
        const settings = await apiGet<Exclusions>(
          "/admin/plagiarism-exclusions",
        );
        if (cancelled) return;
        setWords(asLines(settings.words));
        setPhrases(asLines(settings.phrases));
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Could not load plagiarism exclusions.",
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
      const updated = await apiSend<Exclusions>(
        "PUT",
        "/admin/plagiarism-exclusions",
        { words: parseLines(words), phrases: parseLines(phrases) },
      );
      setWords(asLines(updated.words));
      setPhrases(asLines(updated.phrases));
      setNotice("Plagiarism exclusions saved.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not save plagiarism exclusions.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <h1>Plagiarism Exclusions</h1>
      <p className="muted">
        Configure words and phrases that should not contribute to plagiarism
        comparisons. Terms are matched without regard to capitalization.
      </p>
      <ErrorBox message={error} />
      {notice && <div className="notice">{notice}</div>}
      <form className="card exclusion-settings" onSubmit={save}>
        <label>
          Words to exclude
          <textarea
            rows={8}
            value={words}
            onChange={(event) => setWords(event.target.value)}
            placeholder={"Example:\nreport\naircraft"}
            disabled={loading || saving}
          />
          <span className="muted">Enter one word per line (up to 500 words).</span>
        </label>
        <label>
          Phrases to exclude
          <textarea
            rows={8}
            value={phrases}
            onChange={(event) => setPhrases(event.target.value)}
            placeholder={"Example:\nin accordance with\nas described above"}
            disabled={loading || saving}
          />
          <span className="muted">
            Enter one phrase per line (up to 500 phrases).
          </span>
        </label>
        <div className="row">
          <button className="btn" type="submit" disabled={loading || saving}>
            {loading ? "Loading…" : saving ? "Saving…" : "Save exclusions"}
          </button>
        </div>
      </form>
    </>
  );
}
