import { useEffect, type ReactNode } from "react";

export function ErrorBox({ message }: { message: string | null }) {
  return message ? <div className="error">{message}</div> : null;
}

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div className="modal-back" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}

const STATUS_COLOURS: Record<string, string> = {
  APPROVED: "green",
  ACTIVE: "green",
  GENERATED: "green",
  COMPLETED: "green",
  VALID: "green",
  PENDING: "orange",
  PROCESSING: "orange",
  REJECTED: "red",
  REVOKED: "red",
  FAILED: "red",
  INACTIVE: "red",
  DELETED: "red",
  CANCELLED: "grey",
};

export function StatusPill({ status }: { status?: string | null }) {
  if (!status) return <span className="pill grey">—</span>;
  const colour = STATUS_COLOURS[status.toUpperCase()] ?? "grey";
  return <span className={`pill ${colour}`}>{status}</span>;
}

export function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatPercent(value?: number | string | null): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "string") return value;
  return `${Math.round(value * 100) / 100}%`;
}
