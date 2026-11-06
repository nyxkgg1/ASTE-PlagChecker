--
-- PostgreSQL database dump
--

\restrict fLXjNOOKKaZUP88T7xJ1xhpCljNb1ogx796EFKCyTY8geUZFWhbsqgUpMVpnodV

-- Dumped from database version 17.11
-- Dumped by pg_dump version 17.11 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ai_detection_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_detection_results (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    scan_id uuid NOT NULL,
    initiated_by uuid NOT NULL,
    model_id uuid,
    ai_probability numeric(5,2),
    confidence character varying(30),
    detected_signals jsonb,
    status character varying(30) DEFAULT 'PROCESSING'::character varying NOT NULL,
    algorithm_version character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ai_probability_check CHECK (((ai_probability IS NULL) OR ((ai_probability >= (0)::numeric) AND (ai_probability <= (100)::numeric)))),
    CONSTRAINT ai_status_check CHECK (((status)::text = ANY ((ARRAY['PROCESSING'::character varying, 'COMPLETED'::character varying, 'FAILED'::character varying])::text[])))
);


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid,
    action character varying(100) NOT NULL,
    entity_type character varying(100),
    entity_id uuid,
    old_values jsonb,
    new_values jsonb,
    ip_address inet,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: certificates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.certificates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    scan_id uuid NOT NULL,
    certificate_number character varying(100) NOT NULL,
    certificate_path text NOT NULL,
    generated_at timestamp with time zone DEFAULT now() NOT NULL,
    generated_by uuid,
    certificate_hash character(64),
    status character varying(30) DEFAULT 'GENERATED'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT certificate_status_check CHECK (((status)::text = ANY ((ARRAY['GENERATED'::character varying, 'REVOKED'::character varying])::text[])))
);


--
-- Name: document_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    request_type character varying(20) NOT NULL,
    requested_by uuid NOT NULL,
    reference_document_id uuid,
    scan_id uuid,
    title text,
    reason text,
    status character varying(30) DEFAULT 'PENDING'::character varying NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp with time zone,
    rejection_reason text,
    admin_comments text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT document_request_status_check CHECK (((status)::text = ANY ((ARRAY['PENDING'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying, 'CANCELLED'::character varying])::text[]))),
    CONSTRAINT document_request_type_check CHECK (((request_type)::text = ANY ((ARRAY['ADD'::character varying, 'UPDATE'::character varying, 'DELETE'::character varying])::text[])))
);


--
-- Name: fter_section_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fter_section_results (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    validation_id uuid NOT NULL,
    template_section_id uuid NOT NULL,
    detected_section_id uuid,
    detection_status character varying(50) NOT NULL,
    confidence numeric(5,2),
    warning_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT fter_confidence_check CHECK (((confidence IS NULL) OR ((confidence >= (0)::numeric) AND (confidence <= (100)::numeric)))),
    CONSTRAINT fter_detection_status_check CHECK (((detection_status)::text = ANY ((ARRAY['PRESENT'::character varying, 'MISSING_WARNING'::character varying, 'OPTIONAL_NOT_PRESENT'::character varying, 'POSSIBLE_MISMATCH'::character varying, 'POSSIBLE_ORDER_MISMATCH'::character varying, 'ADDITIONAL'::character varying])::text[])))
);


--
-- Name: fter_template_sections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fter_template_sections (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    template_id uuid NOT NULL,
    parent_section_id uuid,
    section_name text NOT NULL,
    normalized_name text NOT NULL,
    section_order integer NOT NULL,
    section_level integer NOT NULL,
    is_required boolean DEFAULT true NOT NULL,
    is_optional boolean DEFAULT false NOT NULL,
    matching_threshold numeric(5,2) DEFAULT 80.00 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT fter_required_optional_check CHECK ((NOT ((is_required = true) AND (is_optional = true)))),
    CONSTRAINT fter_section_level_check CHECK ((section_level >= 1)),
    CONSTRAINT fter_section_order_check CHECK ((section_order >= 1)),
    CONSTRAINT fter_section_threshold_check CHECK (((matching_threshold >= (0)::numeric) AND (matching_threshold <= (100)::numeric)))
);


--
-- Name: fter_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fter_templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    template_name character varying(255) NOT NULL,
    version character varying(50) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: fter_validation_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fter_validation_results (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    scan_id uuid NOT NULL,
    template_id uuid NOT NULL,
    warning_count integer DEFAULT 0 NOT NULL,
    info_count integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT fter_info_count_check CHECK ((info_count >= 0)),
    CONSTRAINT fter_warning_count_check CHECK ((warning_count >= 0))
);


--
-- Name: model_registry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_registry (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    model_name character varying(255) NOT NULL,
    model_type character varying(50) NOT NULL,
    version character varying(100),
    local_path text NOT NULL,
    model_hash character(64),
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: plagiarism_analyses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plagiarism_analyses (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    scan_id uuid NOT NULL,
    initiated_by uuid NOT NULL,
    status character varying(30) DEFAULT 'PROCESSING'::character varying NOT NULL,
    overall_similarity numeric(5,2),
    exact_match_score numeric(5,2),
    ngram_score numeric(5,2),
    tfidf_score numeric(5,2),
    semantic_score numeric(5,2),
    cross_encoder_score numeric(5,2),
    algorithm_version character varying(100),
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT plagiarism_analysis_status_check CHECK (((status)::text = ANY ((ARRAY['PROCESSING'::character varying, 'COMPLETED'::character varying, 'FAILED'::character varying])::text[]))),
    CONSTRAINT plagiarism_overall_score_check CHECK (((overall_similarity IS NULL) OR ((overall_similarity >= (0)::numeric) AND (overall_similarity <= (100)::numeric))))
);


--
-- Name: plagiarism_matches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plagiarism_matches (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    analysis_id uuid NOT NULL,
    reference_document_id uuid NOT NULL,
    scan_sentence_id uuid,
    reference_sentence_id uuid,
    detection_method character varying(50) NOT NULL,
    similarity_score numeric(5,2),
    scan_page_number integer,
    reference_page_number integer,
    scan_text text,
    reference_text text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT plagiarism_match_score_check CHECK (((similarity_score IS NULL) OR ((similarity_score >= (0)::numeric) AND (similarity_score <= (100)::numeric))))
);


--
-- Name: reference_document_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reference_document_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    reference_document_id uuid NOT NULL,
    version_number integer NOT NULL,
    file_name text NOT NULL,
    file_path text NOT NULL,
    sha256_hash character(64) NOT NULL,
    uploaded_by uuid NOT NULL,
    approved_by uuid,
    approved_at timestamp with time zone,
    change_reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT reference_version_number_check CHECK ((version_number >= 1))
);


--
-- Name: reference_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reference_documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    title text NOT NULL,
    document_type character varying(50) DEFAULT 'FTER'::character varying NOT NULL,
    file_name text NOT NULL,
    file_path text NOT NULL,
    file_size bigint,
    mime_type character varying(100),
    sha256_hash character(64) NOT NULL,
    status character varying(30) DEFAULT 'ACTIVE'::character varying NOT NULL,
    current_version integer DEFAULT 1 NOT NULL,
    added_by uuid NOT NULL,
    approved_by uuid NOT NULL,
    approved_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT reference_documents_status_check CHECK (((status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'ARCHIVED'::character varying, 'DELETED'::character varying])::text[]))),
    CONSTRAINT reference_documents_version_check CHECK ((current_version >= 1))
);


--
-- Name: reference_embeddings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reference_embeddings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    sentence_id uuid NOT NULL,
    model_id uuid,
    embedding public.vector(1024) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: reference_sentences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reference_sentences (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    reference_document_id uuid NOT NULL,
    version_id uuid NOT NULL,
    page_number integer,
    section_title text,
    sentence_index integer,
    raw_text text NOT NULL,
    normalized_text text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roles (
    id integer NOT NULL,
    role_name character varying(50) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: roles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.roles_id_seq OWNED BY public.roles.id;


--
-- Name: scan_embeddings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scan_embeddings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    sentence_id uuid NOT NULL,
    model_id uuid,
    embedding public.vector(1024) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: scan_pages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scan_pages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    scan_id uuid NOT NULL,
    page_number integer NOT NULL,
    raw_text text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT scan_pages_page_number_check CHECK ((page_number > 0))
);


--
-- Name: scan_sections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scan_sections (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    scan_id uuid NOT NULL,
    parent_section_id uuid,
    section_title text NOT NULL,
    normalized_title text,
    section_level integer,
    section_order integer,
    page_start integer,
    page_end integer,
    detection_confidence numeric(5,2),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT scan_sections_confidence_check CHECK (((detection_confidence IS NULL) OR ((detection_confidence >= (0)::numeric) AND (detection_confidence <= (100)::numeric))))
);


--
-- Name: scan_sentences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scan_sentences (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    scan_id uuid NOT NULL,
    page_id uuid,
    section_id uuid,
    sentence_index integer NOT NULL,
    raw_text text NOT NULL,
    normalized_text text,
    token_count integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT scan_sentences_index_check CHECK ((sentence_index >= 0))
);


--
-- Name: scans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scans (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    title text NOT NULL,
    file_name text NOT NULL,
    file_path text NOT NULL,
    file_size bigint,
    mime_type character varying(100),
    sha256_hash character(64) NOT NULL,
    scanned_by uuid NOT NULL,
    owner_id uuid,
    status character varying(30) DEFAULT 'UPLOADED'::character varying NOT NULL,
    processing_started_at timestamp with time zone,
    processing_completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT scans_status_check CHECK (((status)::text = ANY ((ARRAY['UPLOADED'::character varying, 'PROCESSING'::character varying, 'COMPLETED'::character varying, 'FAILED'::character varying])::text[])))
);


--
-- Name: student_officer_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.student_officer_profiles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    service_number character varying(100),
    course character varying(255),
    batch character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: system_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_settings (
    key character varying(100) NOT NULL,
    value text,
    description text,
    updated_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_roles (
    user_id uuid NOT NULL,
    role_id integer NOT NULL,
    assigned_by uuid,
    assigned_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    username character varying(100) NOT NULL,
    email character varying(255) NOT NULL,
    full_name character varying(255) NOT NULL,
    password_hash text NOT NULL,
    status character varying(20) DEFAULT 'ACTIVE'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_login_at timestamp with time zone,
    deactivated_at timestamp with time zone,
    deleted_at timestamp with time zone,
    CONSTRAINT users_status_check CHECK (((status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'INACTIVE'::character varying, 'DELETED'::character varying])::text[])))
);


--
-- Name: roles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles ALTER COLUMN id SET DEFAULT nextval('public.roles_id_seq'::regclass);


--
-- Name: ai_detection_results ai_detection_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_detection_results
    ADD CONSTRAINT ai_detection_results_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: certificates certificates_certificate_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificates
    ADD CONSTRAINT certificates_certificate_number_key UNIQUE (certificate_number);


--
-- Name: certificates certificates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificates
    ADD CONSTRAINT certificates_pkey PRIMARY KEY (id);


--
-- Name: certificates certificates_scan_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificates
    ADD CONSTRAINT certificates_scan_id_key UNIQUE (scan_id);


--
-- Name: document_requests document_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_requests
    ADD CONSTRAINT document_requests_pkey PRIMARY KEY (id);


--
-- Name: fter_section_results fter_section_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fter_section_results
    ADD CONSTRAINT fter_section_results_pkey PRIMARY KEY (id);


--
-- Name: fter_template_sections fter_template_sections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fter_template_sections
    ADD CONSTRAINT fter_template_sections_pkey PRIMARY KEY (id);


--
-- Name: fter_templates fter_template_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fter_templates
    ADD CONSTRAINT fter_template_unique UNIQUE (template_name, version);


--
-- Name: fter_templates fter_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fter_templates
    ADD CONSTRAINT fter_templates_pkey PRIMARY KEY (id);


--
-- Name: fter_validation_results fter_validation_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fter_validation_results
    ADD CONSTRAINT fter_validation_results_pkey PRIMARY KEY (id);


--
-- Name: model_registry model_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_registry
    ADD CONSTRAINT model_registry_pkey PRIMARY KEY (id);


--
-- Name: plagiarism_analyses plagiarism_analyses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plagiarism_analyses
    ADD CONSTRAINT plagiarism_analyses_pkey PRIMARY KEY (id);


--
-- Name: plagiarism_matches plagiarism_matches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plagiarism_matches
    ADD CONSTRAINT plagiarism_matches_pkey PRIMARY KEY (id);


--
-- Name: reference_document_versions reference_document_version_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_document_versions
    ADD CONSTRAINT reference_document_version_unique UNIQUE (reference_document_id, version_number);


--
-- Name: reference_document_versions reference_document_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_document_versions
    ADD CONSTRAINT reference_document_versions_pkey PRIMARY KEY (id);


--
-- Name: reference_documents reference_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_documents
    ADD CONSTRAINT reference_documents_pkey PRIMARY KEY (id);


--
-- Name: reference_embeddings reference_embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_embeddings
    ADD CONSTRAINT reference_embeddings_pkey PRIMARY KEY (id);


--
-- Name: reference_sentences reference_sentences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_sentences
    ADD CONSTRAINT reference_sentences_pkey PRIMARY KEY (id);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: roles roles_role_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_role_name_key UNIQUE (role_name);


--
-- Name: scan_embeddings scan_embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scan_embeddings
    ADD CONSTRAINT scan_embeddings_pkey PRIMARY KEY (id);


--
-- Name: scan_pages scan_pages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scan_pages
    ADD CONSTRAINT scan_pages_pkey PRIMARY KEY (id);


--
-- Name: scan_pages scan_pages_unique_page; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scan_pages
    ADD CONSTRAINT scan_pages_unique_page UNIQUE (scan_id, page_number);


--
-- Name: scan_sections scan_sections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scan_sections
    ADD CONSTRAINT scan_sections_pkey PRIMARY KEY (id);


--
-- Name: scan_sentences scan_sentences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scan_sentences
    ADD CONSTRAINT scan_sentences_pkey PRIMARY KEY (id);


--
-- Name: scans scans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scans
    ADD CONSTRAINT scans_pkey PRIMARY KEY (id);


--
-- Name: student_officer_profiles student_officer_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_officer_profiles
    ADD CONSTRAINT student_officer_profiles_pkey PRIMARY KEY (id);


--
-- Name: student_officer_profiles student_officer_profiles_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_officer_profiles
    ADD CONSTRAINT student_officer_profiles_user_id_key UNIQUE (user_id);


--
-- Name: system_settings system_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_settings
    ADD CONSTRAINT system_settings_pkey PRIMARY KEY (key);


--
-- Name: user_roles user_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (user_id, role_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: idx_ai_detection_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_detection_created_at ON public.ai_detection_results USING btree (created_at);


--
-- Name: idx_ai_detection_scan; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_detection_scan ON public.ai_detection_results USING btree (scan_id);


--
-- Name: idx_audit_logs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_logs_created_at ON public.audit_logs USING btree (created_at);


--
-- Name: idx_audit_logs_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_logs_entity ON public.audit_logs USING btree (entity_type, entity_id);


--
-- Name: idx_audit_logs_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_logs_user ON public.audit_logs USING btree (user_id);


--
-- Name: idx_certificates_generated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_certificates_generated_at ON public.certificates USING btree (generated_at);


--
-- Name: idx_document_requests_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_requests_created_at ON public.document_requests USING btree (created_at);


--
-- Name: idx_document_requests_reference_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_requests_reference_document ON public.document_requests USING btree (reference_document_id);


--
-- Name: idx_document_requests_requested_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_requests_requested_by ON public.document_requests USING btree (requested_by);


--
-- Name: idx_document_requests_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_requests_status ON public.document_requests USING btree (status);


--
-- Name: idx_fter_section_results_validation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fter_section_results_validation ON public.fter_section_results USING btree (validation_id);


--
-- Name: idx_fter_template_sections_template; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fter_template_sections_template ON public.fter_template_sections USING btree (template_id);


--
-- Name: idx_fter_validation_scan; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fter_validation_scan ON public.fter_validation_results USING btree (scan_id);


--
-- Name: idx_plagiarism_analyses_scan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_plagiarism_analyses_scan_id ON public.plagiarism_analyses USING btree (scan_id);


--
-- Name: idx_plagiarism_matches_analysis_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_plagiarism_matches_analysis_id ON public.plagiarism_matches USING btree (analysis_id);


--
-- Name: idx_plagiarism_matches_reference_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_plagiarism_matches_reference_document ON public.plagiarism_matches USING btree (reference_document_id);


--
-- Name: idx_reference_documents_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reference_documents_status ON public.reference_documents USING btree (status);


--
-- Name: idx_reference_documents_title; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reference_documents_title ON public.reference_documents USING btree (title);


--
-- Name: idx_reference_embeddings_vector; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reference_embeddings_vector ON public.reference_embeddings USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_reference_sentences_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reference_sentences_document ON public.reference_sentences USING btree (reference_document_id);


--
-- Name: idx_reference_sentences_version; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reference_sentences_version ON public.reference_sentences USING btree (version_id);


--
-- Name: idx_scan_embeddings_vector; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scan_embeddings_vector ON public.scan_embeddings USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_scan_pages_scan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scan_pages_scan_id ON public.scan_pages USING btree (scan_id);


--
-- Name: idx_scan_sections_scan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scan_sections_scan_id ON public.scan_sections USING btree (scan_id);


--
-- Name: idx_scan_sentences_page_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scan_sentences_page_id ON public.scan_sentences USING btree (page_id);


--
-- Name: idx_scan_sentences_scan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scan_sentences_scan_id ON public.scan_sentences USING btree (scan_id);


--
-- Name: idx_scans_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scans_created_at ON public.scans USING btree (created_at);


--
-- Name: idx_scans_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scans_owner_id ON public.scans USING btree (owner_id);


--
-- Name: idx_scans_scanned_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scans_scanned_by ON public.scans USING btree (scanned_by);


--
-- Name: idx_scans_sha256; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scans_sha256 ON public.scans USING btree (sha256_hash);


--
-- Name: idx_scans_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scans_status ON public.scans USING btree (status);


--
-- Name: idx_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_email ON public.users USING btree (email);


--
-- Name: idx_users_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_status ON public.users USING btree (status);


--
-- Name: ai_detection_results fk_ai_result_scan; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_detection_results
    ADD CONSTRAINT fk_ai_result_scan FOREIGN KEY (scan_id) REFERENCES public.scans(id) ON DELETE CASCADE;


--
-- Name: ai_detection_results fk_ai_result_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_detection_results
    ADD CONSTRAINT fk_ai_result_user FOREIGN KEY (initiated_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: audit_logs fk_audit_logs_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT fk_audit_logs_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: certificates fk_certificates_generated_by; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificates
    ADD CONSTRAINT fk_certificates_generated_by FOREIGN KEY (generated_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: certificates fk_certificates_scan; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificates
    ADD CONSTRAINT fk_certificates_scan FOREIGN KEY (scan_id) REFERENCES public.scans(id) ON DELETE RESTRICT;


--
-- Name: document_requests fk_document_requests_reference; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_requests
    ADD CONSTRAINT fk_document_requests_reference FOREIGN KEY (reference_document_id) REFERENCES public.reference_documents(id) ON DELETE RESTRICT;


--
-- Name: document_requests fk_document_requests_requested_by; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_requests
    ADD CONSTRAINT fk_document_requests_requested_by FOREIGN KEY (requested_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: document_requests fk_document_requests_reviewed_by; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_requests
    ADD CONSTRAINT fk_document_requests_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: document_requests fk_document_requests_scan; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_requests
    ADD CONSTRAINT fk_document_requests_scan FOREIGN KEY (scan_id) REFERENCES public.scans(id) ON DELETE RESTRICT;


--
-- Name: fter_section_results fk_fter_section_result_detected; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fter_section_results
    ADD CONSTRAINT fk_fter_section_result_detected FOREIGN KEY (detected_section_id) REFERENCES public.scan_sections(id) ON DELETE SET NULL;


--
-- Name: fter_section_results fk_fter_section_result_template; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fter_section_results
    ADD CONSTRAINT fk_fter_section_result_template FOREIGN KEY (template_section_id) REFERENCES public.fter_template_sections(id) ON DELETE RESTRICT;


--
-- Name: fter_section_results fk_fter_section_result_validation; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fter_section_results
    ADD CONSTRAINT fk_fter_section_result_validation FOREIGN KEY (validation_id) REFERENCES public.fter_validation_results(id) ON DELETE CASCADE;


--
-- Name: fter_template_sections fk_fter_template_sections_parent; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fter_template_sections
    ADD CONSTRAINT fk_fter_template_sections_parent FOREIGN KEY (parent_section_id) REFERENCES public.fter_template_sections(id) ON DELETE CASCADE;


--
-- Name: fter_template_sections fk_fter_template_sections_template; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fter_template_sections
    ADD CONSTRAINT fk_fter_template_sections_template FOREIGN KEY (template_id) REFERENCES public.fter_templates(id) ON DELETE CASCADE;


--
-- Name: fter_templates fk_fter_templates_created_by; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fter_templates
    ADD CONSTRAINT fk_fter_templates_created_by FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: fter_validation_results fk_fter_validation_scan; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fter_validation_results
    ADD CONSTRAINT fk_fter_validation_scan FOREIGN KEY (scan_id) REFERENCES public.scans(id) ON DELETE CASCADE;


--
-- Name: fter_validation_results fk_fter_validation_template; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fter_validation_results
    ADD CONSTRAINT fk_fter_validation_template FOREIGN KEY (template_id) REFERENCES public.fter_templates(id) ON DELETE RESTRICT;


--
-- Name: plagiarism_analyses fk_plagiarism_analysis_scan; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plagiarism_analyses
    ADD CONSTRAINT fk_plagiarism_analysis_scan FOREIGN KEY (scan_id) REFERENCES public.scans(id) ON DELETE CASCADE;


--
-- Name: plagiarism_analyses fk_plagiarism_analysis_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plagiarism_analyses
    ADD CONSTRAINT fk_plagiarism_analysis_user FOREIGN KEY (initiated_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: plagiarism_matches fk_plagiarism_matches_analysis; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plagiarism_matches
    ADD CONSTRAINT fk_plagiarism_matches_analysis FOREIGN KEY (analysis_id) REFERENCES public.plagiarism_analyses(id) ON DELETE CASCADE;


--
-- Name: plagiarism_matches fk_plagiarism_matches_reference_document; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plagiarism_matches
    ADD CONSTRAINT fk_plagiarism_matches_reference_document FOREIGN KEY (reference_document_id) REFERENCES public.reference_documents(id) ON DELETE RESTRICT;


--
-- Name: plagiarism_matches fk_plagiarism_matches_reference_sentence; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plagiarism_matches
    ADD CONSTRAINT fk_plagiarism_matches_reference_sentence FOREIGN KEY (reference_sentence_id) REFERENCES public.reference_sentences(id) ON DELETE SET NULL;


--
-- Name: plagiarism_matches fk_plagiarism_matches_scan_sentence; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plagiarism_matches
    ADD CONSTRAINT fk_plagiarism_matches_scan_sentence FOREIGN KEY (scan_sentence_id) REFERENCES public.scan_sentences(id) ON DELETE SET NULL;


--
-- Name: reference_documents fk_reference_documents_added_by; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_documents
    ADD CONSTRAINT fk_reference_documents_added_by FOREIGN KEY (added_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: reference_documents fk_reference_documents_approved_by; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_documents
    ADD CONSTRAINT fk_reference_documents_approved_by FOREIGN KEY (approved_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: reference_embeddings fk_reference_embeddings_sentence; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_embeddings
    ADD CONSTRAINT fk_reference_embeddings_sentence FOREIGN KEY (sentence_id) REFERENCES public.reference_sentences(id) ON DELETE CASCADE;


--
-- Name: reference_sentences fk_reference_sentences_document; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_sentences
    ADD CONSTRAINT fk_reference_sentences_document FOREIGN KEY (reference_document_id) REFERENCES public.reference_documents(id) ON DELETE CASCADE;


--
-- Name: reference_sentences fk_reference_sentences_version; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_sentences
    ADD CONSTRAINT fk_reference_sentences_version FOREIGN KEY (version_id) REFERENCES public.reference_document_versions(id) ON DELETE CASCADE;


--
-- Name: reference_document_versions fk_reference_versions_approved_by; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_document_versions
    ADD CONSTRAINT fk_reference_versions_approved_by FOREIGN KEY (approved_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: reference_document_versions fk_reference_versions_document; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_document_versions
    ADD CONSTRAINT fk_reference_versions_document FOREIGN KEY (reference_document_id) REFERENCES public.reference_documents(id) ON DELETE CASCADE;


--
-- Name: reference_document_versions fk_reference_versions_uploaded_by; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_document_versions
    ADD CONSTRAINT fk_reference_versions_uploaded_by FOREIGN KEY (uploaded_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: scan_embeddings fk_scan_embeddings_sentence; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scan_embeddings
    ADD CONSTRAINT fk_scan_embeddings_sentence FOREIGN KEY (sentence_id) REFERENCES public.scan_sentences(id) ON DELETE CASCADE;


--
-- Name: scan_pages fk_scan_pages_scan; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scan_pages
    ADD CONSTRAINT fk_scan_pages_scan FOREIGN KEY (scan_id) REFERENCES public.scans(id) ON DELETE CASCADE;


--
-- Name: scan_sections fk_scan_sections_parent; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scan_sections
    ADD CONSTRAINT fk_scan_sections_parent FOREIGN KEY (parent_section_id) REFERENCES public.scan_sections(id) ON DELETE CASCADE;


--
-- Name: scan_sections fk_scan_sections_scan; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scan_sections
    ADD CONSTRAINT fk_scan_sections_scan FOREIGN KEY (scan_id) REFERENCES public.scans(id) ON DELETE CASCADE;


--
-- Name: scan_sentences fk_scan_sentences_page; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scan_sentences
    ADD CONSTRAINT fk_scan_sentences_page FOREIGN KEY (page_id) REFERENCES public.scan_pages(id) ON DELETE CASCADE;


--
-- Name: scan_sentences fk_scan_sentences_scan; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scan_sentences
    ADD CONSTRAINT fk_scan_sentences_scan FOREIGN KEY (scan_id) REFERENCES public.scans(id) ON DELETE CASCADE;


--
-- Name: scan_sentences fk_scan_sentences_section; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scan_sentences
    ADD CONSTRAINT fk_scan_sentences_section FOREIGN KEY (section_id) REFERENCES public.scan_sections(id) ON DELETE SET NULL;


--
-- Name: scans fk_scans_owner; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scans
    ADD CONSTRAINT fk_scans_owner FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: scans fk_scans_scanned_by; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scans
    ADD CONSTRAINT fk_scans_scanned_by FOREIGN KEY (scanned_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: student_officer_profiles fk_student_profile_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_officer_profiles
    ADD CONSTRAINT fk_student_profile_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: system_settings fk_system_settings_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_settings
    ADD CONSTRAINT fk_system_settings_user FOREIGN KEY (updated_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: user_roles fk_user_roles_assigned_by; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT fk_user_roles_assigned_by FOREIGN KEY (assigned_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: user_roles fk_user_roles_role; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT fk_user_roles_role FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE RESTRICT;


--
-- Name: user_roles fk_user_roles_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--

\unrestrict fLXjNOOKKaZUP88T7xJ1xhpCljNb1ogx796EFKCyTY8geUZFWhbsqgUpMVpnodV

