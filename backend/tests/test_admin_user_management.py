import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.api.routes.admin import assign_role, create_user
from app.models.user import User, UserRole
from app.schemas.admin import CreateUserRequest, RoleAssignmentRequest


class AdminUserManagementTests(unittest.TestCase):
    def test_assigning_role_replaces_previous_role(self):
        user_id = uuid4()
        old_assignment = SimpleNamespace(
            role_id=1,
            role=SimpleNamespace(role_name="INSTRUCTOR"),
        )
        user = SimpleNamespace(
            id=user_id,
            status="ACTIVE",
            user_roles=[old_assignment],
        )
        role = SimpleNamespace(id=2, role_name="STUDENT_OFFICER")
        user_query = MagicMock()
        role_query = MagicMock()
        user_query.filter.return_value.first.return_value = user
        role_query.filter.return_value.first.return_value = role
        db = MagicMock()
        db.query.side_effect = [user_query, role_query]

        with (
            patch("app.api.routes.admin.create_audit_log"),
            patch("app.api.routes.admin.serialize_user", return_value="serialized"),
        ):
            result = assign_role(
                user_id=str(user_id),
                request=RoleAssignmentRequest(role_name="STUDENT_OFFICER"),
                db=db,
                current_admin=SimpleNamespace(id=uuid4()),
            )

        self.assertEqual(result, "serialized")
        db.delete.assert_called_once_with(old_assignment)
        added_role = db.add.call_args.args[0]
        self.assertIsInstance(added_role, UserRole)
        self.assertEqual(added_role.role_id, role.id)
        db.commit.assert_called_once()

    def test_creating_user_ignores_deleted_username(self):
        username_query = MagicMock()
        email_query = MagicMock()
        role_query = MagicMock()
        username_query.filter.return_value.first.return_value = None
        email_query.filter.return_value.first.return_value = None
        role_query.filter.return_value.first.return_value = SimpleNamespace(
            id=1,
            role_name="INSTRUCTOR",
        )
        db = MagicMock()
        db.query.side_effect = [username_query, email_query, role_query]

        with (
            patch("app.api.routes.admin.hash_password", return_value="hashed"),
            patch("app.api.routes.admin.create_audit_log"),
            patch("app.api.routes.admin.serialize_user", return_value="serialized"),
        ):
            result = create_user(
                request=CreateUserRequest(
                    username="aaa",
                    email="aaa@example.com",
                    full_name="Test User",
                    password="password123",
                    role_name="INSTRUCTOR",
                ),
                db=db,
                current_admin=SimpleNamespace(id=uuid4()),
            )

        self.assertEqual(result, "serialized")
        username_filter = username_query.filter.call_args.args
        status_filter = username_filter[1]
        self.assertIn("users.status !=", str(status_filter))
        self.assertIn("DELETED", status_filter.compile().params.values())
        db.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
