
from pydantic import BaseModel, Field


# ============================================================
# Scan Responses
# ============================================================

class ScanResponse(BaseModel):
    id: str
    title: str
    file_name: str
    file_size: int
    mime_type: str
    sha256_hash: str
    status: str
    owner_id: str | None
    scanned_by: str
    created_at: str
    completed_at: str | None


class ScanPageResponse(BaseModel):
    id: str
    page_number: int
    text: str


class ScanSentenceResponse(BaseModel):
    id: str
    page_number: int
    sentence_index: int
    text: str
    token_count: int


# ============================================================
# Plagiarism Statistics
# ============================================================

class PlagiarismStatisticsResponse(BaseModel):
    total_sentences: int
    matched_sentences: int
    unmatched_sentences: int

    sentence_coverage_percentage: float
    text_coverage_percentage: float
    average_match_strength: float


# ============================================================
# Algorithm Scores
# ============================================================

class PlagiarismAlgorithmScoresResponse(BaseModel):
    exact: float | None
    ngram: float | None
    tfidf: float | None
    semantic: float | None
    cross_encoder: float | None


# ============================================================
# Match Counts
# ============================================================

class PlagiarismMatchCountsResponse(BaseModel):
    exact: int
    high_similarity: int
    moderate_similarity: int
    low_similarity: int


# ============================================================
# Individual Plagiarism Match
# ============================================================

class PlagiarismMatchResponse(BaseModel):
    id: str

    sentence_index: int

    scan_page_number: int | None

    match_type: str

    similarity_score: float

    source: str

    reference_page_number: int | None

    scan_text: str | None

    reference_text: str | None


# ============================================================
# Unmatched Sentence
# ============================================================

class UnmatchedSentenceResponse(BaseModel):
    sentence_index: int
    scan_page_number: int | None
    text: str
    token_count: int


# ============================================================
# Complete Plagiarism Result
# ============================================================

class PlagiarismResultResponse(BaseModel):
    scan_id: str

    analysis_id: str

    status: str

    # Final document-level plagiarism score.
    # Stored internally as 0.0 - 1.0.
    overall_similarity: float | None
    ai_score: float | None = None
    ai_confidence: float | None = None
    ai_status: str | None = None
    ai_model: str | None = None
    ai_explanation: str | None = None

    statistics: PlagiarismStatisticsResponse

    algorithm_scores: PlagiarismAlgorithmScoresResponse

    match_counts: PlagiarismMatchCountsResponse

    matches: list[PlagiarismMatchResponse]

    unmatched_sentences: list[
        UnmatchedSentenceResponse
    ]

class PlagiarismSourceSummaryResponse(BaseModel):
    source: str
    matched_sentences: int
    average_similarity: float


class PlagiarismPageSummaryResponse(BaseModel):
    page_number: int
    total_sentences: int
    matched_sentences: int
    sentence_coverage_percentage: float


class PlagiarismReportResponse(BaseModel):
    scan_id: str
    analysis_id: str

    document_title: str
    file_name: str
    scanned_by: str
    scanned_on: str
    completed_on: str | None

    status: str
    overall_similarity: float | None
    ai_score: float | None = None
    ai_confidence: float | None = None
    ai_status: str | None = None
    ai_model: str | None = None
    ai_explanation: str | None = None

    statistics: PlagiarismStatisticsResponse
    algorithm_scores: PlagiarismAlgorithmScoresResponse
    match_counts: PlagiarismMatchCountsResponse

    source_summary: list[PlagiarismSourceSummaryResponse]
    page_summary: list[PlagiarismPageSummaryResponse]

    matches: list[PlagiarismMatchResponse]
    unmatched_sentences: list[UnmatchedSentenceResponse]

class CompareReferenceDocumentResponse(BaseModel):
    id: str
    title: str
    file_name: str
    match_count: int


class CompareMatchResponse(BaseModel):
    match_id: str
    reference_document_id: str
    reference_title: str
    reference_file_name: str

    sentence_index: int
    section_title: str | None = None
    paragraph_title: str | None = None

    scan_page_number: int | None
    reference_page_number: int | None

    match_type: str
    similarity_score: float

    scan_text: str | None
    reference_text: str | None

    scan_highlighting: dict
    reference_highlighting: dict


class PlagiarismCompareResponse(BaseModel):
    scan_id: str
    analysis_id: str

    scan_title: str
    scan_file_name: str

    reference_documents: list[
        CompareReferenceDocumentResponse
    ]

    matches: list[CompareMatchResponse]

# ============================================================
# Certificate
# ============================================================

class CertificateResponse(BaseModel):
    id: str
    scan_id: str
    certificate_number: str
    certificate_path: str
    generated_at: str
    generated_by: str
    certificate_hash: str | None
    status: str


class CertificateGenerationRequest(BaseModel):
    student_name: str = Field(min_length=1, max_length=255)
    service_number: str | None = Field(default=None, max_length=100)
    course: str | None = Field(default=None, max_length=255)
    batch: str | None = Field(default=None, max_length=100)