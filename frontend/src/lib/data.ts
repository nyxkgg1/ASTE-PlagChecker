import { useCallback, useEffect, useState } from "react";

// Backend list endpoints may return a bare array or an envelope such as
// { items: [...] }. Accept both so the UI keeps working if that changes.
export function toArray<T = Record<string, unknown>>(
  value: unknown
): T[] {
  if (Array.isArray(value)) return value as T[];

  if (value && typeof value === "object") {
    for (const key of [
      "items",
      "results",
      "data",
      "sentences",
      "matches",
      "logs",
      "users",
      "requests",
      "certificates",
      "documents",
      "scans",
      "pages",
    ]) {
      const inner = (value as Record<string, unknown>)[key];

      if (Array.isArray(inner)) return inner as T[];
    }
  }

  return [];
}

// First non-empty value among several possible field names.
export function pick(row: Record<string, unknown>, ...keys: string[]): unknown {
  for (const key of keys) {
    const value = row[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return undefined;
}

export function pickString(row: Record<string, unknown>, ...keys: string[]): string {
  const value = pick(row, ...keys);
  return value === undefined ? "" : String(value);
}

// Scores: the database stores 0–100, but some responses are fractions
// (0.35). Treat values up to 1 as fractions so both display correctly.
export function scoreToPercent(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const number = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(number)) return null;
  const percent = number <= 1 ? number * 100 : number;
  return Math.round(percent * 100) / 100;
}

export function percentageValue(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) return null;
  return Math.round(number * 100) / 100;
}

export function useLoad<T>(loader: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const stableLoader = useCallback(loader, deps);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    stableLoader()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Request failed");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [stableLoader, tick]);

  return { data, error, loading, reload: () => setTick((n) => n + 1) };
}
