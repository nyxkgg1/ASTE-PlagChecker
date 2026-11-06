from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.dependencies import require_roles
from app.services.model_comparison_service import (
    compare_models,
    get_model_catalog,
)


router = APIRouter(
    prefix="/admin/model-comparer",
    tags=["Model comparer"],
    dependencies=[Depends(require_roles("ADMIN"))],
)


class ComparisonCase(BaseModel):
    text_a: str = Field(min_length=1, max_length=12_000)
    text_b: str = Field(min_length=1, max_length=12_000)
    similar: bool


class ComparisonRequest(BaseModel):
    cases: list[ComparisonCase] = Field(min_length=4, max_length=200)
    repetitions: int = Field(default=3, ge=1, le=10)


@router.get("/models")
def list_models() -> list[dict[str, Any]]:
    return get_model_catalog()


@router.post("/run")
def run_comparison(
    request: ComparisonRequest,
) -> dict[str, Any]:
    cases = [case.model_dump() for case in request.cases]
    positive_count = sum(case["similar"] for case in cases)
    negative_count = len(cases) - positive_count
    if positive_count < 2 or negative_count < 2:
        raise HTTPException(
            status_code=422,
            detail=(
                "Provide at least two similar and two dissimilar pairs "
                "to calculate meaningful benchmark metrics."
            ),
        )

    try:
        return compare_models(cases, request.repetitions)
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
