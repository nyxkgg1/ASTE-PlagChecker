BEGIN;

-- Running upgrade 66aed157c25e -> 4d4e0d87b526

CREATE TABLE ai_generated_content (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    generated_text TEXT NOT NULL, 
    normalized_text TEXT NOT NULL, 
    content_hash VARCHAR(64) NOT NULL, 
    source_model VARCHAR(150), 
    source_version VARCHAR(100), 
    generation_date TIMESTAMP WITH TIME ZONE, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_ai_generated_content_hash ON ai_generated_content (content_hash);

CREATE INDEX ix_ai_generated_content_fts
        ON ai_generated_content
        USING gin (to_tsvector('english', normalized_text));

CREATE TABLE ai_generated_content_embeddings (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    content_id UUID NOT NULL, 
    model_id UUID NOT NULL, 
    embedding VECTOR(1024) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT fk_ai_content_embeddings_content FOREIGN KEY(content_id) REFERENCES ai_generated_content (id) ON DELETE CASCADE, 
    CONSTRAINT fk_ai_content_embeddings_model FOREIGN KEY(model_id) REFERENCES model_registry (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_ai_content_embedding_model UNIQUE (content_id, model_id)
);

CREATE INDEX ix_ai_content_embeddings_model_id ON ai_generated_content_embeddings (model_id);

CREATE INDEX ix_ai_content_embeddings_vector_hnsw
        ON ai_generated_content_embeddings
        USING hnsw (embedding vector_cosine_ops);

UPDATE alembic_version SET version_num='4d4e0d87b526' WHERE alembic_version.version_num = '66aed157c25e';

COMMIT;

