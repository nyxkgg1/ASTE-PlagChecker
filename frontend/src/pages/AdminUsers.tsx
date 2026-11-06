import { useState, type ChangeEvent, type FormEvent } from "react";
import { apiGet, apiSend } from "../api/client";
import type { UserRow } from "../api/types";
import { ErrorBox, Modal, StatusPill } from "../components/ui";
import { toArray, useLoad } from "../lib/data";

const ROLES = ["ADMIN", "INSTRUCTOR", "STUDENT_OFFICER"];

export default function AdminUsers() {
  const { data, error, loading, reload } = useLoad(() => apiGet<unknown>("/admin/users"), []);
  const users = toArray<UserRow>(data);
  const [actionError, setActionError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [roleFor, setRoleFor] = useState<UserRow | null>(null);

  async function run(action: () => Promise<unknown>) {
    setActionError(null);
    try {
      await action();
      reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed");
    }
  }

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
        <h1 style={{ margin: 0 }}>User Management</h1>
        <button className="btn" onClick={() => setCreateOpen(true)}>
          + Create user
        </button>
      </div>
      <ErrorBox message={error ?? actionError} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Sr No.</th>
              <th>Username</th>
              <th>Name</th>
              <th>Email</th>
              <th>Roles</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={7}>Loading…</td>
              </tr>
            )}
            {users.map((user, index) => (
              <tr key={user.id}>
                <td>{index + 1}</td>
                <td className="left">{user.username}</td>
                <td className="left">{user.full_name}</td>
                <td className="left">{user.email}</td>
                <td>{(user.roles ?? []).join(", ") || "—"}</td>
                <td>
                  <StatusPill status={user.status} />
                </td>
                <td>
                  <div className="row" style={{ justifyContent: "center", gap: 6 }}>
                    {user.status === "ACTIVE" ? (
                      <button
                        className="btn small ghost"
                        onClick={() => run(() => apiSend("PATCH", `/admin/users/${user.id}/deactivate`))}
                      >
                        Deactivate
                      </button>
                    ) : (
                      user.status !== "DELETED" && (
                        <button
                          className="btn small green"
                          onClick={() => run(() => apiSend("PATCH", `/admin/users/${user.id}/activate`))}
                        >
                          Activate
                        </button>
                      )
                    )}
                    <button className="btn small ghost" onClick={() => setRoleFor(user)}>
                      Assign role
                    </button>
                    {user.status !== "DELETED" && (
                      <button
                        className="btn small red"
                        onClick={() => {
                          if (window.confirm(`Delete user “${user.username}”?`)) {
                            run(() => apiSend("DELETE", `/admin/users/${user.id}`));
                          }
                        }}
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {createOpen && (
        <CreateUserModal
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            setCreateOpen(false);
            reload();
          }}
        />
      )}
      {roleFor && (
        <AssignRoleModal
          user={roleFor}
          onClose={() => setRoleFor(null)}
          onDone={() => {
            setRoleFor(null);
            reload();
          }}
        />
      )}
    </>
  );
}

function CreateUserModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({
    username: "",
    email: "",
    full_name: "",
    password: "",
    role_name: "INSTRUCTOR",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (key: keyof typeof form) => (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiSend("POST", "/admin/users", form);
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create user");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Create user" onClose={onClose}>
      <form onSubmit={submit}>
        <ErrorBox message={error} />
        <label>
          Username
          <input value={form.username} onChange={set("username")} required />
        </label>
        <label>
          Full name
          <input value={form.full_name} onChange={set("full_name")} required />
        </label>
        <label>
          Email
          <input type="email" value={form.email} onChange={set("email")} required />
        </label>
        <label>
          Password (min 8 characters)
          <input type="password" minLength={8} value={form.password} onChange={set("password")} required />
        </label>
        <label>
          Role
          <select value={form.role_name} onChange={set("role_name")}>
            {ROLES.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </label>
        <div className="btns">
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn" disabled={busy}>
            {busy ? "Creating…" : "Create"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function AssignRoleModal({
  user,
  onClose,
  onDone,
}: {
  user: UserRow;
  onClose: () => void;
  onDone: () => void;
}) {
  const [role, setRole] = useState(user.roles?.[0] ?? ROLES[0]);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await apiSend("POST", `/admin/users/${user.id}/roles`, { role_name: role });
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not assign role");
    }
  }

  return (
    <Modal title={`Assign role to ${user.username}`} onClose={onClose}>
      <form onSubmit={submit}>
        <ErrorBox message={error} />
        <label>
          Role
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </label>
        <div className="btns">
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn">Assign</button>
        </div>
      </form>
    </Modal>
  );
}
