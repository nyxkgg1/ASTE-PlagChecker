from uuid import uuid4
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User, Role, UserRole
from app.models.scan import Scan
from app.models.ai_analysis import AIAnalysisRun, AIDetectorResult


# ---------------------------------------------------------
# Test configuration
# ---------------------------------------------------------

marker = uuid4().hex[:12]
created_user_ids = []
created_scan_id = None
created_run_id = None
detector_id = None

db = SessionLocal()
client = TestClient(app)

try:
    # -----------------------------------------------------
    # 1. Load existing roles
    # -----------------------------------------------------

    roles = {
        role.role_name: role
        for role in db.query(Role).filter(
            Role.role_name.in_([
                "ADMIN",
                "INSTRUCTOR",
                "STUDENT_OFFICER",
            ])
        ).all()
    }

    required_roles = {
        "ADMIN",
        "INSTRUCTOR",
        "STUDENT_OFFICER",
    }

    assert required_roles.issubset(roles.keys()), (
        f"Missing roles: {required_roles - roles.keys()}"
    )

    # -----------------------------------------------------
    # 2. Create three temporary users
    # -----------------------------------------------------

    admin = User(
        username=f"test_admin_{marker}",
        email=f"test_admin_{marker}@example.test",
        full_name="Temporary Test Admin",
        password_hash="test-only-not-a-real-password-hash",
        status="ACTIVE",
    )

    owner = User(
        username=f"test_owner_{marker}",
        email=f"test_owner_{marker}@example.test",
        full_name="Temporary Test Owner",
        password_hash="test-only-not-a-real-password-hash",
        status="ACTIVE",
    )

    outsider = User(
        username=f"test_outsider_{marker}",
        email=f"test_outsider_{marker}@example.test",
        full_name="Temporary Test Outsider",
        password_hash="test-only-not-a-real-password-hash",
        status="ACTIVE",
    )

    db.add_all([admin, owner, outsider])
    db.flush()

    created_user_ids = [
        admin.id,
        owner.id,
        outsider.id,
    ]

    db.add_all([
        UserRole(user_id=admin.id, role_id=roles["ADMIN"].id),
        UserRole(user_id=owner.id, role_id=roles["INSTRUCTOR"].id),
        UserRole(
            user_id=outsider.id,
            role_id=roles["STUDENT_OFFICER"].id,
        ),
    ])

    # -----------------------------------------------------
    # 3. Create temporary scan
    # -----------------------------------------------------

    scan = Scan(
        title=f"Temporary AI explanation API test {marker}",
        file_name=f"test_{marker}.pdf",
        file_path=f"/tmp/test_{marker}.pdf",
        file_size=100,
        mime_type="application/pdf",
        sha256_hash="a" * 64,
        scanned_by=owner.id,
        owner_id=owner.id,
        status="COMPLETED",
    )

    db.add(scan)
    db.flush()
    created_scan_id = scan.id

    # -----------------------------------------------------
    # 4. Create completed AI analysis run
    # -----------------------------------------------------

    run = AIAnalysisRun(
        scan_id=scan.id,
        initiated_by=owner.id,
        status="COMPLETED",
    )

    db.add(run)
    db.flush()
    created_run_id = run.id

    # -----------------------------------------------------
    # 5. Create completed detector result
    # -----------------------------------------------------

    original_score = Decimal("42.50")
    original_explanation = (
        "Original deterministic explanation for integration testing."
    )

    detector = AIDetectorResult(
        run_id=run.id,
        detector_type="LINGUISTIC_HEURISTIC",
        detector_version="test-version-1",
        status="COMPLETED",
        score=original_score,
        score_semantics="LINGUISTIC_INDICATOR",
        confidence=Decimal("0.750"),
        metrics={
            "test_metric": 1,
            "test_marker": marker,
        },
        explanation=original_explanation,
    )

    db.add(detector)
    db.commit()
    db.refresh(detector)

    detector_id = detector.id

    print("\nTemporary test data created.")
    print("Detector result ID:", detector_id)

    # -----------------------------------------------------
    # 6. Generate JWT tokens
    # -----------------------------------------------------

    admin_token = create_access_token(
        str(admin.id),
        admin.username,
        ["ADMIN"],
    )

    owner_token = create_access_token(
        str(owner.id),
        owner.username,
        ["INSTRUCTOR"],
    )

    outsider_token = create_access_token(
        str(outsider.id),
        outsider.username,
        ["STUDENT_OFFICER"],
    )

    generate_url = (
        f"/ai-detector-explanations/{detector_id}/generate"
    )

    history_url = (
        f"/ai-detector-explanations/"
        f"detector-results/{detector_id}/history"
    )

    # -----------------------------------------------------
    # 7. Authentication test
    # -----------------------------------------------------

    response = client.get(history_url)

    assert response.status_code in (401, 403), (
        f"Unexpected unauthenticated response: "
        f"{response.status_code} {response.text}"
    )

    print("PASS: Unauthenticated request rejected.")

    # -----------------------------------------------------
    # 8. Owner access and successful generation
    # -----------------------------------------------------

    mock_success = {
        "detector_result_id": str(detector_id),
        "model_name": "qwen3.5:4b",
        "prompt_version": "ai-detector-explanation-v1",
        "explanation_text": (
            "This is a mocked supplementary explanation. "
            "The linguistic indicator score is not proof "
            "of AI authorship."
        ),
        "generation_metadata": {
            "test_mode": True,
            "provider": "mock",
        },
    }

    with patch(
        "app.services.ai_detector_explanation_orchestrator."
        "generate_prepared_detector_explanation",
        return_value=mock_success,
    ) as mocked_generator:

        response = client.post(
            generate_url,
            headers={
                "Authorization": f"Bearer {owner_token}"
            },
        )

    assert response.status_code == 200, (
        f"Generation failed: {response.status_code} "
        f"{response.text}"
    )

    success_data = response.json()

    assert success_data["status"] == "COMPLETED"
    assert success_data["explanation_text"] == (
        mock_success["explanation_text"]
    )
    assert mocked_generator.called

    print("PASS: Scan owner can generate an explanation.")
    print("PASS: Mocked generation persisted as COMPLETED.")

    # -----------------------------------------------------
    # 9. Outsider access must be denied
    # -----------------------------------------------------

    response = client.get(
        history_url,
        headers={
            "Authorization": f"Bearer {outsider_token}"
        },
    )

    assert response.status_code == 403, (
        f"Expected 403, received {response.status_code}: "
        f"{response.text}"
    )

    print("PASS: Unrelated user denied access.")

    # -----------------------------------------------------
    # 10. Admin access to explanation history
    # -----------------------------------------------------

    response = client.get(
        history_url,
        headers={
            "Authorization": f"Bearer {admin_token}"
        },
    )

    assert response.status_code == 200, response.text

    history = response.json()

    assert history["count"] == 1
    assert history["items"][0]["status"] == "COMPLETED"

    print("PASS: Admin can access explanation history.")

    # -----------------------------------------------------
    # 11. Simulate Qwen generation failure
    # -----------------------------------------------------

    with patch(
        "app.services.ai_detector_explanation_orchestrator."
        "generate_prepared_detector_explanation",
        side_effect=RuntimeError("Simulated Ollama failure"),
    ):

        response = client.post(
            generate_url,
            headers={
                "Authorization": f"Bearer {owner_token}"
            },
        )

    assert response.status_code == 200, (
        f"Failure handling returned unexpected response: "
        f"{response.status_code} {response.text}"
    )

    failed_data = response.json()

    assert failed_data["status"] == "FAILED"
    assert failed_data["explanation_text"] is None
    assert failed_data["error_message"]

    print("PASS: Generation failure persisted as FAILED.")

    # -----------------------------------------------------
    # 12. Verify history contains both attempts
    # -----------------------------------------------------

    response = client.get(
        history_url,
        headers={
            "Authorization": f"Bearer {owner_token}"
        },
    )

    assert response.status_code == 200, response.text

    history = response.json()

    assert history["count"] == 2

    statuses = {
        item["status"]
        for item in history["items"]
    }

    assert statuses == {"COMPLETED", "FAILED"}

    print("PASS: History contains COMPLETED and FAILED.")

    # -----------------------------------------------------
    # 13. Verify original detector result is unchanged
    # -----------------------------------------------------

    db.expire_all()

    unchanged_detector = (
        db.query(AIDetectorResult)
        .filter(AIDetectorResult.id == detector_id)
        .one()
    )

    assert unchanged_detector.score == original_score
    assert unchanged_detector.explanation == original_explanation
    assert unchanged_detector.score_semantics == (
        "LINGUISTIC_INDICATOR"
    )
    assert unchanged_detector.metrics == {
        "test_metric": 1,
        "test_marker": marker,
    }

    print("PASS: Original score is unchanged.")
    print("PASS: Original deterministic explanation is unchanged.")
    print("PASS: Original metrics and score semantics are unchanged.")

    print("\nALL INTEGRATION TESTS PASSED.")

finally:
    # -----------------------------------------------------
    # 14. Clean up only records created by this test
    # -----------------------------------------------------

    try:
        db.rollback()

        if created_run_id is not None:
            db.query(AIAnalysisRun).filter(
                AIAnalysisRun.id == created_run_id
            ).delete(synchronize_session=False)

        if created_scan_id is not None:
            db.query(Scan).filter(
                Scan.id == created_scan_id
            ).delete(synchronize_session=False)

        if created_user_ids:
            db.query(UserRole).filter(
                UserRole.user_id.in_(created_user_ids)
            ).delete(synchronize_session=False)

            db.query(User).filter(
                User.id.in_(created_user_ids)
            ).delete(synchronize_session=False)

        db.commit()
        print("\nTemporary test records cleaned up.")

    except Exception as cleanup_error:
        db.rollback()
        print("\nWARNING: Cleanup failed:", repr(cleanup_error))
        raise

    finally:
        client.close()
        db.close()
