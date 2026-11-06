from app.models.ai_detector_explanation import (
    AIDetectorExplanation,
)

from app.models.ai_generated_content import (
    AIGeneratedContent,
    AIGeneratedContentEmbedding,
)

from app.models.ai_analysis import (
    AIAnalysisRun,
    AIDetectorResult,
    AIDetectorEvidence,
)

from app.models.user import (
    User,
    Role,
    UserRole,
    StudentOfficerProfile,
)

from app.models.model_registry import (
    ModelRegistry,
)

from app.models.scan import (
    Scan,
    ScanPage,
    ScanSection,
    ScanSentence,
    ScanEmbedding,
)

from app.models.reference import (
    ReferenceDocument,
    ReferenceDocumentVersion,
    ReferenceSentence,
    ReferenceEmbedding,
)

from app.models.plagiarism import (
    PlagiarismAnalysis,
    PlagiarismMatch,
    DocumentRequest,
)

from app.models.fter import (
    FTERTemplate,
    FTERTemplateSection,
    FTERValidationResult,
    FTERSectionResult,
)

from app.models.ai_detection import (
    AIDetectionResult,
)

from app.models.certificate import (
    Certificate,
)

from app.models.audit import (
    AuditLog,
)

from app.models.system_setting import (
    SystemSetting,
)

from app.db.base import Base

from app.models.user import (
    User,
    Role,
    UserRole,
    StudentOfficerProfile,
)

from app.models.model_registry import (
    ModelRegistry,
)

from app.models.scan import (
    Scan,
    ScanPage,
    ScanSection,
    ScanSentence,
    ScanEmbedding,
)

from app.models.reference import (
    ReferenceDocument,
    ReferenceDocumentVersion,
    ReferenceSentence,
    ReferenceEmbedding,
)

from app.models.plagiarism import (
    PlagiarismAnalysis,
    PlagiarismMatch,
    DocumentRequest,
)

from app.models.fter import (
    FTERTemplate,
    FTERTemplateSection,
    FTERValidationResult,
    FTERSectionResult,
)

from app.models.ai_detection import (
    AIDetectionResult,
)

from app.models.certificate import (
    Certificate,
)

from app.models.audit import (
    AuditLog,
)

from app.models.plagiarism_fingerprint import ReferenceSentenceFingerprint

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Index,
)