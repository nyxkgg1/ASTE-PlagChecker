BEGIN;

-- Running upgrade f2a0c6d93e81 -> 66aed157c25e

CREATE TABLE ai_analysis_runs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    scan_id UUID NOT NULL, 
    initiated_by UUID NOT NULL, 
    status VARCHAR(30) DEFAULT 'PROCESSING' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_ai_analysis_runs_status CHECK (
            status IN (
                'PROCESSING',
                'COMPLETED',
                'PARTIAL_COMPLETED',
                'FAILED',
                'NOT_CONFIGURED'
            )
            ), 
    CONSTRAINT fk_ai_analysis_runs_scan FOREIGN KEY(scan_id) REFERENCES scans (id) ON DELETE CASCADE, 
    CONSTRAINT fk_ai_analysis_runs_initiated_by FOREIGN KEY(initiated_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX idx_ai_analysis_runs_scan_created ON ai_analysis_runs (scan_id, created_at);

CREATE INDEX idx_ai_analysis_runs_status ON ai_analysis_runs (status);

CREATE TABLE ai_detector_results (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    run_id UUID NOT NULL, 
    detector_type VARCHAR(40) NOT NULL, 
    detector_version VARCHAR(100) NOT NULL, 
    model_id UUID, 
    status VARCHAR(30) DEFAULT 'PROCESSING' NOT NULL, 
    score NUMERIC(5, 2), 
    score_semantics VARCHAR(60), 
    confidence NUMERIC(4, 3), 
    metrics JSONB, 
    explanation TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_ai_detector_results_type CHECK (
            detector_type IN (
                'CLASSIFIER',
                'CORPUS_MATCH',
                'LINGUISTIC_HEURISTIC'
            )
            ), 
    CONSTRAINT ck_ai_detector_results_status CHECK (
            status IN (
                'PROCESSING',
                'COMPLETED',
                'FAILED',
                'NOT_CONFIGURED',
                'NOT_ANALYZED'
            )
            ), 
    CONSTRAINT ck_ai_detector_results_score_range CHECK (score IS NULL OR (score >= 0 AND score <= 100)), 
    CONSTRAINT ck_ai_detector_results_confidence_range CHECK (
            confidence IS NULL
            OR (confidence >= 0 AND confidence <= 1)
            ), 
    CONSTRAINT fk_ai_detector_results_run FOREIGN KEY(run_id) REFERENCES ai_analysis_runs (id) ON DELETE CASCADE, 
    CONSTRAINT fk_ai_detector_results_model FOREIGN KEY(model_id) REFERENCES model_registry (id) ON DELETE SET NULL, 
    CONSTRAINT uq_ai_detector_result_run_type UNIQUE (run_id, detector_type)
);

CREATE INDEX idx_ai_detector_results_run ON ai_detector_results (run_id);

CREATE INDEX idx_ai_detector_results_type_status ON ai_detector_results (detector_type, status);

CREATE TABLE ai_detector_evidence (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    detector_result_id UUID NOT NULL, 
    sentence_id UUID NOT NULL, 
    evidence_type VARCHAR(50) NOT NULL, 
    evidence_score NUMERIC(5, 2), 
    details JSONB, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_ai_detector_evidence_score_range CHECK (
            evidence_score IS NULL
            OR (evidence_score >= 0 AND evidence_score <= 100)
            ), 
    CONSTRAINT fk_ai_detector_evidence_result FOREIGN KEY(detector_result_id) REFERENCES ai_detector_results (id) ON DELETE CASCADE, 
    CONSTRAINT fk_ai_detector_evidence_sentence FOREIGN KEY(sentence_id) REFERENCES scan_sentences (id) ON DELETE CASCADE
);

CREATE INDEX idx_ai_detector_evidence_result ON ai_detector_evidence (detector_result_id);

CREATE INDEX idx_ai_detector_evidence_sentence ON ai_detector_evidence (sentence_id);

UPDATE alembic_version SET version_num='66aed157c25e' WHERE alembic_version.version_num = 'f2a0c6d93e81';

COMMIT;

