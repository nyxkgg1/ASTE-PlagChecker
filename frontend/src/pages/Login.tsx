import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ArrowRight, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { ErrorBox } from "../components/ui";
import { homeFor } from "../components/Layout";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [capsLockOn, setCapsLockOn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homeFor(user.roles)} replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(username.trim(), password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 px-4 py-12">
      {/* Background glow blobs */}
      <div className="login-glow login-glow-one pointer-events-none absolute -left-32 -top-32 h-96 w-96 rounded-full bg-blue-600/25 blur-3xl" />
      <div className="login-glow login-glow-two pointer-events-none absolute -bottom-40 -right-32 h-[28rem] w-[28rem] rounded-full bg-sky-500/20 blur-3xl" />
      <div className="login-orbit login-orbit-one" aria-hidden="true" />
      <div className="login-orbit login-orbit-two" aria-hidden="true" />
      <div
        className="login-grid pointer-events-none absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage:
            "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      <div className="login-shell relative w-full max-w-md">
        {/* Card */}
        <div className="login-card rounded-2xl border border-white/10 bg-white/95 p-8 shadow-2xl shadow-black/40 backdrop-blur-xl sm:p-10">
          {/* Header */}
          <div className="login-brand mb-6 text-center">
            <div className="login-emblem-wrap mx-auto mb-5">
              <span className="login-emblem-halo" aria-hidden="true" />
              <img
                src="/Images/ASTE.jpg"
                alt="Air Force Test Pilots School insignia"
                className="login-insignia relative z-10 h-24 w-auto object-contain"
              />
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Plagiarism Checker
            </h1>
            <p className="mt-1 text-sm font-medium uppercase tracking-widest text-slate-500">
              Airforce Test Pilots School
            </p>
            <div className="login-secure-badge mx-auto mt-5">
              <ShieldCheck size={14} aria-hidden="true" />
              <span>Secure personnel access</span>
            </div>
          </div>

          <form
            onSubmit={submit}
            className="login-form space-y-5"
            aria-busy={busy}
          >
            <div role="alert" aria-live="polite">
              <ErrorBox message={error} />
            </div>

            {/* Username */}
            <div className="login-field login-field-username">
              <label
                htmlFor="username"
                className="mb-1.5 block text-sm font-medium text-slate-700"
              >
                Username
              </label>
              <div className="relative">
                <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.8}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-5 w-5"
                  >
                    <circle cx="12" cy="8" r="4" />
                    <path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" />
                  </svg>
                </span>
                <input
                  id="username"
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value);
                    if (error) setError(null);
                  }}
                  autoComplete="username"
                  placeholder="Enter your username"
                  required
                  autoFocus
                  aria-invalid={Boolean(error)}
                  className="block w-full rounded-xl border border-slate-300 bg-white py-2.5 pl-11 pr-4 text-slate-900 placeholder-slate-400 shadow-sm transition focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/15"
                />
              </div>
            </div>

            {/* Password */}
            <div className="login-field login-field-password">
              <label
                htmlFor="password"
                className="mb-1.5 block text-sm font-medium text-slate-700"
              >
                Password
              </label>
              <div className="relative">
                <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.8}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-5 w-5"
                  >
                    <rect x="4" y="11" width="16" height="10" rx="2" />
                    <path d="M8 11V7a4 4 0 018 0v4" />
                  </svg>
                </span>
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (error) setError(null);
                  }}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  required
                  aria-invalid={Boolean(error)}
                  onKeyDown={(event) =>
                    setCapsLockOn(event.getModifierState("CapsLock"))
                  }
                  onKeyUp={(event) =>
                    setCapsLockOn(event.getModifierState("CapsLock"))
                  }
                  onBlur={() => setCapsLockOn(false)}
                  className="block w-full rounded-xl border border-slate-300 bg-white py-2.5 pl-11 pr-16 text-slate-900 placeholder-slate-400 shadow-sm transition focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/15"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  className="login-password-toggle absolute inset-y-0 right-0 px-4 text-xs font-semibold text-slate-500 transition hover:text-blue-700"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  title={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
              {capsLockOn && (
                <p className="login-caps-lock" role="status">
                  Caps Lock is on
                </p>
              )}
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={busy}
              aria-live="polite"
              className="login-submit group flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-800 to-sky-600 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-800/25 transition hover:from-blue-700 hover:to-sky-500 hover:shadow-blue-700/35 focus:outline-none focus:ring-4 focus:ring-blue-500/30 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-70"
            >
              {busy ? (
                <>
                  <svg
                    className="h-4 w-4 animate-spin"
                    viewBox="0 0 24 24"
                    fill="none"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-90"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                    />
                  </svg>
                  Signing in…
                </>
              ) : (
                <>
                  Sign in
                  <ArrowRight
                    size={17}
                    className="transition-transform group-hover:translate-x-1"
                    aria-hidden="true"
                  />
                </>
              )}
            </button>
            <p className="login-local-note">
              Your sign-in is handled by this local system.
            </p>
          </form>
        </div>

        <p className="login-security-note mt-6 text-center text-xs text-slate-400">
          Authorized personnel only · Activity may be monitored
        </p>
      </div>
    </div>
  );
}
