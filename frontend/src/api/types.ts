// Response shapes used by the UI.
//
// Fields marked "ASSUMED" were inferred from your backend notes rather than
// from real JSON. If a screen shows blanks, compare the Swagger response with
// the type here and adjust the field name (they are used in one place each).

export type Role = "ADMIN" | "INSTRUCTOR" | "STUDENT_OFFICER";

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface UserRow {
  id: string;
  username: string;
  email: string;
  full_name: string;
  status: string;
  roles: string[];
}

export interface Scan {
  id: string;
  title: string;
  file_name?: string;
  status?: string;
  created_at?: string;
  file_size?: 0;
  mime_type?: string;
  sha256_hash?: string;
  owner_id?: string;
  scanned_by?: string;
  completed_at?: string;
  ai_score?: number | null;
  ai_confidence?: number | null;
  ai_status?: string | null;
  ai_model?: string | null;
}

// ASSUMED: POST /scans returns a ScanResponse like this.
export interface ScanResponse extends Scan {
  title: string;
  file_name?: string;
  status?: string;
  created_at?: string;
  file_size?: 0;
  mime_type?: string;
  sha256_hash?: string;
  owner_id?: string;
  scanned_by?: string;
  completed_at?: string;
}

// ASSUMED field names for the plagiarism result.
export interface PlagiarismResult {
  scan_id?: string;
  status?: string;
  overall_similarity?: number | null;
  statistics?: {
    total_sentences: number;
    matched_sentences: number;
    unmatched_sentences: number;
    sentence_coverage_percentage: number;
    text_coverage_percentage: number;
    average_match_strength: number;
  };
  algorithm_scores?: {
    exact: number | null;
    ngram: number | null;
    tfidf: number | null;
    semantic: number | null;
    cross_encoder: number | null;
  };
  match_counts?: {
    exact: number;
    high_similarity: number;
    moderate_similarity: number;
    low_similarity: number;
  };
  ai_score?: number | null;
  ai_confidence?: number | null;
  ai_status?: string | null;
  ai_model?: string | null;
  ai_explanation?: string | null;
  [key: string]: unknown;
}

export interface AIDetectorEvidence {
  id: string;
  sentence_id: string;
  evidence_type: string;
  evidence_score: number | null;
  details: {
    category?: string;
    observation?: string;
    quote?: string;
    sentence_index?: number;
    ai_probability?: number;
    model_confidence?: number;
    visualization_threshold?: number;
    interpretation?: string;
    [key: string]: unknown;
  };
  sentence_text: string;
  created_at: string | null;
}

export interface AIDetectorResult {
  id: string;
  detector_type:
    | "CLASSIFIER"
    | "CORPUS_MATCH"
    | "LINGUISTIC_HEURISTIC"
    | "QWEN_EXPERIMENTAL";
  detector_version: string;
  model_id: string | null;
  status:
    | "PROCESSING"
    | "COMPLETED"
    | "FAILED"
    | "NOT_CONFIGURED"
    | "NOT_ANALYZED";
  score: number | null;
  score_semantics: string | null;
  confidence: number | null;
  metrics: Record<string, unknown> | null;
  explanation: string | null;
  evidence: AIDetectorEvidence[];
  created_at: string | null;
  completed_at: string | null;
}

export interface AIAnalysisResponse {
  scan_id: string;
  status:
    | "NOT_STARTED"
    | "PROCESSING"
    | "COMPLETED"
    | "PARTIAL_COMPLETED"
    | "FAILED"
    | "NOT_CONFIGURED";
  analysis_run: {
    id: string;
    status: string;
    created_at: string | null;
    completed_at: string | null;
  } | null;
  detector_results: AIDetectorResult[];
}

export interface CertificateRow {
  id: string;
  scan_id: string;
  certificate_number: string;
  generated_at?: string;
  status?: string;
  document_title?: string;
  plagiarism_score_percent?: number | null;
  ai_score?: number | null;
  ai_confidence?: number | null;
  ai_status?: string | null;
  user?: { full_name?: string; username?: string } | null;
  generated_by_name?: string | null;
  [key: string]: unknown;
}

export interface ReferenceRequest {
  id: string;
  request_type?: string;
  scan_id?: string | null;
  title?: string | null;
  reason?: string | null;
  status: string;
  pending_file_name?: string | null;
  requested_by?: string;
  requested_by_name?: string;
  created_at?: string;
  [key: string]: unknown;
}

export interface ReferenceDocument {
  id: string;
  title: string;
  document_type?: string;
  file_name?: string;
  file_size?: number | null;
  mime_type?: string | null;
  status?: string;
  current_version?: number;
  created_at?: string;
  [key: string]: unknown;
}

export interface AuditLogRow {
  id: string;
  user_name?: string | null;
  action: string;
  entity_type?: string | null;
  entity_id?: string | null;
  old_values?: unknown;
  new_values?: unknown;
  created_at: string;
}

// ASSUMED pagination envelope: { items: [...], page, page_size, total }.
export interface Paged<T> {
  items: T[];
  page?: number;
  page_size?: number;
  total?: number;
  total_pages?: number;
  pagination?: {
    page?: number;
    page_size?: number;
    total?: number;
    total_pages?: number;
  };
}
