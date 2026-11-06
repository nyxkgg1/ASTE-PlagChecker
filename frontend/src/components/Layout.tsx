import { useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Outlet } from "react-router-dom";
import {
  CalendarClock,
  Clock3,
  LogOut,
  ShieldCheck,
  Timer,
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import type { Role } from "../api/types";

interface NavItem {
  to: string;
  label: string;
  roles: Role[];
}

const NAV: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", roles: ["ADMIN"] },
  { to: "/scan", label: "Generate Certificate", roles: ["ADMIN", "INSTRUCTOR"] },
  { to: "/documents", label: "Previous Documents", roles: ["ADMIN", "INSTRUCTOR", "STUDENT_OFFICER"] },
  { to: "/admin/database", label: "Manage Database", roles: ["ADMIN"] },
  { to: "/admin/model-comparer", label: "Model Comparer", roles: ["ADMIN"] },
  { to: "/admin/users", label: "User Management", roles: ["ADMIN"] },
  { to: "/admin/certificates", label: "Certificates", roles: ["ADMIN"] },
  { to: "/admin/audit-logs", label: "Audit Logs", roles: ["ADMIN"] },
  { to: "/admin/plagiarism-exclusions", label: "Plagiarism Exclusions", roles: ["ADMIN"] },
  { to: "/admin/plagiarism-model", label: "Plagiarism Model", roles: ["ADMIN"] },
];

export function homeFor(roles: Role[]): string {
  if (roles.includes("ADMIN")) return "/dashboard";
  if (roles.includes("INSTRUCTOR")) return "/scan";
  return "/documents";
}

function formatDuration(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1_000));
  const days = Math.floor(totalSeconds / 86_400);
  const hours = Math.floor((totalSeconds % 86_400) / 3_600);
  const minutes = Math.floor((totalSeconds % 3_600) / 60);
  const seconds = totalSeconds % 60;
  if (days > 0) return `${days}d ${hours}h ${minutes}m ${seconds}s`;
  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

export default function Layout() {
  const { user, logout, hasRole } = useAuth();
  const [userCardOpen, setUserCardOpen] = useState(false);
  const [now, setNow] = useState(Date.now());
  const userCardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!userCardOpen) return;
    const interval = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(interval);
  }, [userCardOpen]);

  useEffect(() => {
    if (!userCardOpen) return;
    function closeOnOutsideClick(event: MouseEvent) {
      if (
        event.target instanceof Node &&
        !userCardRef.current?.contains(event.target)
      ) {
        setUserCardOpen(false);
      }
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setUserCardOpen(false);
    }
    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [userCardOpen]);

  if (!user) return <Navigate to="/login" replace />;

  const initials = (user.username || "?").slice(0, 2).toUpperCase();
  const sessionStarted = user.issuedAt
    ? new Date(user.issuedAt).toLocaleString()
    : "Unavailable";
  const sessionElapsed = user.issuedAt
    ? formatDuration(now - user.issuedAt)
    : "Unavailable";
  const sessionExpiry = user.expiresAt
    ? new Date(user.expiresAt).toLocaleString()
    : "Unavailable";
  const sessionRemaining = user.expiresAt
    ? formatDuration(user.expiresAt - now)
    : "Unavailable";
  const roleLabels: Record<Role, string> = {
    ADMIN: "Administrator",
    INSTRUCTOR: "Instructor",
    STUDENT_OFFICER: "Student Officer",
  };
  const userRole = user.roles.map((role) => roleLabels[role]).join(" · ");

  return (
    <>
      <header className="topbar">
        <img
          className="topbar-logo topbar-logo-left"
          src="/Images/logo.png"
          alt="Indian Air Force logo"
        />
        <div className="topbar-title">
          Plagiarism Checker
          <br />
          Airforce Test Pilots School
        </div>
        <div className="topbar-right">
          <img
            className="topbar-logo topbar-logo-right"
            src="/Images/ASTE.jpg"
            alt="Air Force Test Pilots School insignia"
          />
          <div className="user-menu" ref={userCardRef}>
            <button
              type="button"
              className={`user-trigger${userCardOpen ? " is-open" : ""}`}
              aria-label="Open user session menu"
              aria-expanded={userCardOpen}
              aria-haspopup="dialog"
              aria-controls={userCardOpen ? "user-session-card" : undefined}
              onClick={() => setUserCardOpen((open) => !open)}
            >
              <span className="avatar">{initials}</span>
            </button>
            {userCardOpen && (
              <section
                className="user-card"
                id="user-session-card"
                role="dialog"
                aria-label="User session"
              >
                <div className="user-card-hero">
                  <span className="user-card-ambient" aria-hidden="true" />
                  <div className="user-card-profile">
                    <span className="user-card-avatar">{initials}</span>
                    <div className="user-card-identity">
                      <strong>{user.username}</strong>
                      <span>{userRole || "Authenticated user"}</span>
                    </div>
                  </div>
                  <span className="user-card-status">
                    <i aria-hidden="true" />
                    Session active
                  </span>
                </div>
                <div className="user-card-content">
                  <div className="user-card-heading">
                    <div>
                      <strong>Session overview</strong>
                      <span>Your secure access details</span>
                    </div>
                    <ShieldCheck size={19} aria-hidden="true" />
                  </div>
                  <div className="user-card-timing">
                    <div className="user-card-detail">
                      <span className="user-card-detail-icon">
                        <CalendarClock size={16} aria-hidden="true" />
                      </span>
                      <span className="user-card-detail-copy">
                        <span>Session started</span>
                        <strong>{sessionStarted}</strong>
                      </span>
                    </div>
                    <div className="user-card-detail">
                      <span className="user-card-detail-icon">
                        <Clock3 size={16} aria-hidden="true" />
                      </span>
                      <span className="user-card-detail-copy">
                        <span>Duration</span>
                        <strong>{sessionElapsed}</strong>
                      </span>
                    </div>
                    <div className="user-card-detail">
                      <span className="user-card-detail-icon">
                        <CalendarClock size={16} aria-hidden="true" />
                      </span>
                      <span className="user-card-detail-copy">
                        <span>Session expires</span>
                        <strong>{sessionExpiry}</strong>
                      </span>
                    </div>
                    <div className="user-card-detail user-card-detail-remaining">
                      <span className="user-card-detail-icon">
                        <Timer size={16} aria-hidden="true" />
                      </span>
                      <span className="user-card-detail-copy">
                        <span>Time remaining</span>
                        <strong>{sessionRemaining}</strong>
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="user-card-signout"
                    onClick={logout}
                  >
                    <LogOut size={16} aria-hidden="true" />
                    Sign out
                  </button>
                </div>
              </section>
            )}
          </div>
        </div>
      </header>
      <div className="layout">
        <nav className="sidebar">
          {NAV.filter((item) => hasRole(...item.roles)).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => (isActive ? "active" : undefined)}
            >
              {item.label}
            </NavLink>
          ))}
          <div className="spacer" />
          <button className="logout" onClick={logout}>
            Sign out
          </button>
        </nav>
        <main className="content">
          <Outlet />
          <footer className="app-footer">
            <span>Project developed by Air Force Technical College</span>
            <span>License: No project license specified</span>
            <span>ASTEPC-V1.5-AFTPS</span>
          </footer>
        </main>
      </div>
    </>
  );
}
