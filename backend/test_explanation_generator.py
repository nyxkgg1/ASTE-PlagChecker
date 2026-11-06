
from uuid import UUID

from app.db.database import SessionLocal
from app.models.ai_analysis import AIAnalysisRun, AIDetectorResult
from app.services.ai_detector_explanation_generator import (
    generate_detector_explanation,
)


SCAN_ID = UUID("d3b5f9f6-7114-41a4-9150-9bec6837f20a")
USER_ID = UUID("8c5dfa82-d6d3-4243-b10c-60ce2a276efc")


db = SessionLocal()

try:
    run = AIAnalysisRun(
        scan_id=SCAN_ID,
        initiated_by=USER_ID,
        status="COMPLETED",
    )
    db.add(run)
    db.flush()

    detector = AIDetectorResult(
        run_id=run.id,
        detector_type="LINGUISTIC_HEURISTIC",
        detector_version="test-v1",
        status="COMPLETED",
        score=42.50,
        score_semantics="LINGUISTIC_INDICATOR",
        confidence=0.750,
        metrics={
            "word_count": 250,
            "sentence_length_variation": 0.35,
            "lexical_diversity": 0.62,
            "repetition_ratio": 0.12,
        },
        explanation=(
            "Preliminary linguistic indicator based on "
            "sentence-length variation, lexical diversity "
            "and repetition. This is not proof of AI authorship."
        ),
    )
    db.add(detector)
    db.flush()

    original_score = detector.score
    original_explanation = detector.explanation

    print("Generating explanation using local Qwen model...")
    print("Model:", "qwen3.5:4b")

    output = generate_detector_explanation(
        db,
        detector_result_id=detector.id,
    )

    print("\n========== QWEN OUTPUT ==========\n")
    print(output["explanation_text"])
    print("\n=================================\n")

    print("Model:", output["model_name"])
    print("Prompt version:", output["prompt_version"])
    print("Metadata:", output["generation_metadata"])

    db.refresh(detector)

    assert detector.score == original_score
    assert detector.explanation == original_explanation

    assert output["explanation_text"].strip()

    print("\nPASS: Actual Qwen generation successful")
    print("PASS: Original detector score unchanged")
    print("PASS: Original deterministic explanation unchanged")

finally:
    db.rollback()
    db.close()
    print("\nROLLBACK COMPLETE")

