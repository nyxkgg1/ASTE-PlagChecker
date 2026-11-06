import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi import HTTPException

from app.api.routes.admin import list_admin_audit_logs, router


class AdminAuditLogTests(unittest.TestCase):
    def test_only_one_audit_log_list_route_is_registered(self):
        matching_routes = [
            route
            for route in router.routes
            if getattr(route, "path", None) == "/admin/audit-logs"
            and "GET" in getattr(route, "methods", set())
        ]

        self.assertEqual(len(matching_routes), 1)
        self.assertEqual(
            matching_routes[0].endpoint,
            list_admin_audit_logs,
        )

    def test_list_applies_all_filters_and_returns_pagination(self):
        user_id = uuid4()
        created_at = datetime(2026, 10, 22, 12, 30, tzinfo=timezone.utc)
        log = SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            action="USER_CREATED",
            entity_type="USER",
            entity_id=uuid4(),
            old_values=None,
            new_values={"username": "pilot"},
            ip_address=None,
            created_at=created_at,
        )
        # Mock the audit-log query.
        query = MagicMock()
        query.filter.return_value = query
        query.order_by.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query
        query.count.return_value = 1
        query.all.return_value = [log]

        # Mock the separate user lookup query.
        user_record = SimpleNamespace(
            id=user_id,
            full_name="Pilot User",
        )

        user_query = MagicMock()
        user_query.filter.return_value = user_query
        user_query.all.return_value = [user_record]

        # Return the appropriate query for each model.
        db = MagicMock()
        db.query.side_effect = [query, user_query]
        start_date = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 10, 22, 13, 0, tzinfo=timezone.utc)

        response = list_admin_audit_logs(
            page=2,
            page_size=10,
            action="USER_CREATED",
            entity_type="USER",
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            db=db,
            current_user=SimpleNamespace(),
        )

        self.assertEqual(query.filter.call_count, 5)
        action_filter = str(query.filter.call_args_list[0].args[0]).lower()
        entity_filter = str(query.filter.call_args_list[1].args[0]).lower()
        self.assertIn("lower(audit_logs.action)", action_filter)
        self.assertIn("like", action_filter)
        self.assertIn("lower(audit_logs.entity_type)", entity_filter)
        self.assertIn("like", entity_filter)
        self.assertEqual(response["items"][0]["id"], str(log.id))
        self.assertEqual(
    response["items"][0]["user_name"],
    "Pilot User",
)
        self.assertEqual(
            response["pagination"],
            {
                "page": 2,
                "page_size": 10,
                "total": 1,
                "total_pages": 1,
            },
        )
        query.offset.assert_called_once_with(10)
        query.limit.assert_called_once_with(10)

    def test_rejects_reversed_date_range(self):
        db = MagicMock()

        with self.assertRaises(HTTPException) as error:
            list_admin_audit_logs(
                page=1,
                page_size=20,
                action=None,
                entity_type=None,
                user_id=None,
                start_date=datetime(2026, 10, 23, tzinfo=timezone.utc),
                end_date=datetime(2026, 10, 22, tzinfo=timezone.utc),
                db=db,
                current_user=SimpleNamespace(),
            )

        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(
            error.exception.detail,
            "start_date must not be after end_date.",
        )


if __name__ == "__main__":
    unittest.main()
