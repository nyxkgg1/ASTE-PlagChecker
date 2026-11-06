import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import Layout, { homeFor } from "./components/Layout";
import RequireRole from "./components/RequireRole";
import AdminAuditLogs from "./pages/AdminAuditLogs";
import AdminCertificates from "./pages/AdminCertificates";
import AdminDatabase from "./pages/AdminDatabase";
import AdminUsers from "./pages/AdminUsers";
import AdminDashboard from "./pages/AdminDashboard";
import AdminModelComparer from "./pages/AdminModelComparer";
import AdminPlagiarismExclusions from "./pages/AdminPlagiarismExclusions";
import AdminPlagiarismModel from "./pages/AdminPlagiarismModel";
import Documents from "./pages/Documents";
import Login from "./pages/Login";
import Scan from "./pages/Scan";

function Home() {
  const { user } = useAuth();
  return <Navigate to={user ? homeFor(user.roles) : "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route
          path="dashboard"
          element={
            <RequireRole roles={["ADMIN"]}>
              <AdminDashboard />
            </RequireRole>
          }
        />
        <Route
          path="scan"
          element={
            <RequireRole roles={["ADMIN", "INSTRUCTOR"]}>
              <Scan />
            </RequireRole>
          }
        />
        <Route path="documents" element={<Documents />} />
        <Route
          path="admin/database"
          element={
            <RequireRole roles={["ADMIN"]}>
              <AdminDatabase />
            </RequireRole>
          }
        />
        <Route
          path="admin/model-comparer"
          element={
            <RequireRole roles={["ADMIN"]}>
              <AdminModelComparer />
            </RequireRole>
          }
        />
        <Route
          path="admin/users"
          element={
            <RequireRole roles={["ADMIN"]}>
              <AdminUsers />
            </RequireRole>
          }
        />
        <Route
          path="admin/certificates"
          element={
            <RequireRole roles={["ADMIN"]}>
              <AdminCertificates />
            </RequireRole>
          }
        />
        <Route
          path="admin/audit-logs"
          element={
            <RequireRole roles={["ADMIN"]}>
              <AdminAuditLogs />
            </RequireRole>
          }
        />
        <Route
          path="admin/plagiarism-exclusions"
          element={
            <RequireRole roles={["ADMIN"]}>
              <AdminPlagiarismExclusions />
            </RequireRole>
          }
        />
        <Route
          path="admin/plagiarism-model"
          element={
            <RequireRole roles={["ADMIN"]}>
              <AdminPlagiarismModel />
            </RequireRole>
          }
        />
      </Route>
      <Route path="*" element={<Home />} />
    </Routes>
  );
}
