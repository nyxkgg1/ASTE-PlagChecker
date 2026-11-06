import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import type { Role } from "../api/types";
import { homeFor } from "./Layout";

// Hides a page from roles that cannot use it. The backend still enforces
// access; this just avoids showing screens that would only return 403.
export default function RequireRole({
  roles,
  children,
}: {
  roles: Role[];
  children: ReactNode;
}) {
  const { user, hasRole } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!hasRole(...roles)) return <Navigate to={homeFor(user.roles)} replace />;
  return <>{children}</>;
}
