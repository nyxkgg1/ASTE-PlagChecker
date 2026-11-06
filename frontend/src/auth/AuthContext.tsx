import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { apiSend, getToken, onUnauthorized, setToken } from "../api/client";
import type { LoginResponse, Role } from "../api/types";

export interface CurrentUser {
  id: string;
  username: string;
  roles: Role[];
  issuedAt: number | null;
  expiresAt: number | null;
}

interface AuthValue {
  user: CurrentUser | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  hasRole: (...roles: Role[]) => boolean;
}

const AuthContext = createContext<AuthValue | null>(null);

// /auth/me returns encrypted data (only the server holds the key), so the
// role list is read from the signed JWT payload instead. The server still
// enforces every permission; this only decides which menu items to show.
function decodeToken(token: string): CurrentUser | null {
  try {
    const part = token.split(".")[1];
    const json = atob(part.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(part.length / 4) * 4, "="));
    const payload = JSON.parse(json);
    if (!payload.sub) return null;
    return {
      id: String(payload.sub),
      username: String(payload.username ?? ""),
      roles: Array.isArray(payload.roles) ? (payload.roles as Role[]) : [],
      issuedAt: typeof payload.iat === "number" ? payload.iat * 1000 : null,
      expiresAt: typeof payload.exp === "number" ? payload.exp * 1000 : null,
    };
  } catch {
    return null;
  }
}

function userFromStoredToken(): CurrentUser | null {
  const token = getToken();
  if (!token) return null;
  const user = decodeToken(token);
  if (!user) return null;
  if (user.expiresAt && user.expiresAt <= Date.now()) {
    setToken(null);
    return null;
  }
  return user;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(userFromStoredToken);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    onUnauthorized(logout);
    return () => onUnauthorized(null);
  }, [logout]);

  // Sign out automatically when the token expires.
  useEffect(() => {
    if (!user?.expiresAt) return;
    const delay = user.expiresAt - Date.now();
    if (delay <= 0) {
      logout();
      return;
    }
    const timer = window.setTimeout(logout, Math.min(delay, 2_147_483_000));
    return () => window.clearTimeout(timer);
  }, [user, logout]);

  const login = useCallback(async (username: string, password: string) => {
    const response = await apiSend<LoginResponse>("POST", "/auth/login", {
      username,
      password,
    });
    const decoded = decodeToken(response.access_token);
    if (!decoded) throw new Error("The server returned an invalid token.");
    setToken(response.access_token);
    setUser(decoded);
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      user,
      login,
      logout,
      hasRole: (...roles: Role[]) => !!user && roles.some((r) => user.roles.includes(r)),
    }),
    [user, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
