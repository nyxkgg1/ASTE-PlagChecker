from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors
from reportlab.pdfgen.canvas import Canvas

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_analysis import AIAnalysisRun, AIDetectorResult
from app.models.certificate import Certificate
from app.models.plagiarism import PlagiarismAnalysis, PlagiarismMatch
from app.models.reference import ReferenceDocument
from app.models.scan import Scan, ScanSentence
from app.models.user import StudentOfficerProfile
from app.services.ai_detector_result_service import (
    classifier_model_confidence,
)


def get_certificate_directory() -> Path:
    """
    Returns the directory where generated certificates are stored.
    """

    upload_dir = Path(settings.upload_dir)

    if not upload_dir.is_absolute():
        upload_dir = (
            Path(__file__).resolve().parents[3]
            / upload_dir
        )

    certificate_dir = upload_dir / "certificates"

    certificate_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    return certificate_dir


def generate_certificate_number() -> str:
    """
    Generates a unique human-readable certificate number.
    """

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d%H%M%S"
    )

    random_part = uuid.uuid4().hex[:6].upper()

    return f"ASTE-CERT-{timestamp}-{random_part}"


def calculate_file_hash(file_path: Path) -> str:
    """
    Calculates SHA-256 hash of the generated certificate.
    """

    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        while True:
            chunk = file.read(1024 * 1024)

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()


def get_latest_completed_analysis(
    db: Session,
    scan: Scan,
) -> PlagiarismAnalysis | None:

    return (
        db.query(PlagiarismAnalysis)
        .filter(
            PlagiarismAnalysis.scan_id == scan.id,
            PlagiarismAnalysis.status == "COMPLETED",
        )
        .order_by(
            PlagiarismAnalysis.completed_at.desc()
        )
        .first()
    )


def generate_certificate_pdf(
    *,
    output_path: Path,
    certificate_number: str,
    scan: Scan,
    student_name: str,
    username: str,
    service_number: str | None,
    course: str | None,
    batch: str | None,
    plagiarism_score: float,
    ai_score: float | None,
    ai_confidence: float | None,
    ai_status: str,
    total_sentences: int,
    matched_sentences: int,
    match_counts: dict[str, int],
    source_summary: list[dict[str, str | int | float]],
    algorithm_scores: dict[str, float | None],
    generated_at: datetime,
) -> None:
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=17 * mm,
        bottomMargin=19 * mm,
    )

    styles = getSampleStyleSheet()
    navy = colors.HexColor("#18324B")
    blue = colors.HexColor("#286B9A")
    pale_blue = colors.HexColor("#EDF5FA")
    pale_gray = colors.HexColor("#F4F6F8")
    muted = colors.HexColor("#5E6B78")
    border = colors.HexColor("#D7E0E7")

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_LEFT,
        textColor=navy,
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        spaceAfter=3,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        textColor=muted,
        fontSize=9,
        leading=13,
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "ReportSection",
        parent=styles["Heading2"],
        textColor=navy,
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        spaceBefore=11,
        spaceAfter=6,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        textColor=navy,
        fontSize=9,
        leading=13,
        spaceAfter=3,
    )
    small_style = ParagraphStyle(
        "ReportSmall",
        parent=styles["BodyText"],
        textColor=muted,
        fontSize=8,
        leading=11,
    )
    label_style = ParagraphStyle(
        "ReportLabel",
        parent=styles["BodyText"],
        textColor=muted,
        fontSize=8,
        leading=10,
    )
    table_header_style = ParagraphStyle(
        "ReportTableHeader",
        parent=label_style,
        textColor=colors.white,
        fontName="Helvetica-Bold",
    )
    score_style = ParagraphStyle(
        "ReportScore",
        parent=styles["BodyText"],
        textColor=navy,
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=23,
    )

    def text(value: object, style: ParagraphStyle = body_style) -> Paragraph:
        return Paragraph(escape(str(value)), style)

    def make_table(
        rows: list[list[object]],
        widths: list[float],
        *,
        header: bool = False,
    ) -> Table:
        table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
        commands = [
            ("GRID", (0, 0), (-1, -1), 0.45, border),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
        if header:
            commands.extend(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), navy),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ]
            )
        elif len(rows) > 0:
            commands.append(("BACKGROUND", (0, 0), (0, -1), pale_gray))
        table.setStyle(TableStyle(commands))
        return table

    def draw_page_footer(canvas: Canvas, doc) -> None:
        canvas.saveState()
        canvas.setStrokeColor(border)
        canvas.line(20 * mm, 14 * mm, A4[0] - 20 * mm, 14 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(muted)
        canvas.drawString(
            20 * mm,
            9 * mm,
            f"ASTE Document Analysis | Certificate {certificate_number}",
        )
        canvas.drawRightString(A4[0] - 20 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    plagiarism_percent = max(0.0, min(100.0, float(plagiarism_score) * 100))
    ai_percent = (
        max(0.0, min(100.0, float(ai_score)))
        if ai_score is not None
        else None
    )
    sentence_coverage = (
        (matched_sentences / total_sentences) * 100
        if total_sentences > 0
        else 0.0
    )
    ai_score_display = (
        f"{ai_percent:.2f}%"
        if ai_percent is not None
        else "Not available"
    )
    ai_explanation = (
        "Experimental model indicator only. It can misclassify writing and "
        "must not be treated as proof of AI authorship. "
        + (
            f"Top-class model confidence: {ai_confidence * 100:.1f}%; "
            "this is not independently validated accuracy."
            if ai_confidence is not None
            else "Model confidence is not available."
        )
        if ai_percent is not None
        else (
            "No completed AI-writing estimate was available when this report "
            "was generated. This is not a zero score."
        )
    )
    story = []
    header = Table(
        [[
            Paragraph(
                "AIRCRAFT AND SYSTEM TESTING ESTABLISHMENT",
                ParagraphStyle(
                    "Organization",
                    parent=body_style,
                    textColor=blue,
                    fontName="Helvetica-Bold",
                    fontSize=9,
                ),
            ),
            Paragraph(
                f"<b>{escape(certificate_number)}</b><br/>"
                f"<font size='8' color='#5E6B78'>"
                f"{generated_at.astimezone().strftime('%d %b %Y, %H:%M')}</font>",
                ParagraphStyle(
                    "CertificateNumber",
                    parent=body_style,
                    alignment=2,
                    fontSize=8,
                ),
            ),
        ]],
        colWidths=[105 * mm, 65 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, blue),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend(
        [
            header,
            Spacer(1, 8 * mm),
            Paragraph("Document analysis certificate", title_style),
            Paragraph(
                "Detailed text similarity and writing analysis",
                subtitle_style,
            ),
            Paragraph("Document and author", section_style),
        ]
    )

    identity_rows = [
        [text("Student officer", label_style), text(student_name)],
        [text("Service number", label_style), text(service_number or "Not provided")],
        [text("Course / batch", label_style), text(" / ".join(part for part in (course, batch) if part) or "Not provided")],
        [text("Document title", label_style), text(scan.title)],
        [text("File", label_style), text(scan.file_name)],
        [text("Account", label_style), text(username)],
    ]
    story.append(make_table(identity_rows, [42 * mm, 128 * mm]))
    story.append(Paragraph("Results at a glance", section_style))

    similarity_card = Table(
        [
            [Paragraph("TEXT SIMILARITY", label_style)],
            [Paragraph(f"{plagiarism_percent:.2f}%", score_style)],
            [
                Paragraph(
                    "Weighted share of document text that resembles material "
                    "in the available reference collection.",
                    small_style,
                )
            ],
        ],
        colWidths=[85 * mm],
    )
    ai_card = Table(
        [
            [Paragraph("AI-WRITING ESTIMATE", label_style)],
            [Paragraph(escape(ai_score_display), score_style)],
            [Paragraph(escape(ai_explanation), small_style)],
        ],
        colWidths=[85 * mm],
    )
    score_cards = Table([[similarity_card, ai_card]], colWidths=[85 * mm, 85 * mm])
    score_cards.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), pale_blue),
                ("BACKGROUND", (1, 0), (1, 0), pale_gray),
                ("BOX", (0, 0), (-1, -1), 0.6, border),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, border),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(score_cards)
    story.append(Spacer(1, 4 * mm))
    story.append(
        text(
            "A similarity result is not, by itself, a finding of plagiarism. "
            "Quoted material, citations, common wording, and legitimate reuse "
            "can all produce matches; review the passages and their sources.",
            small_style,
        )
    )

    story.append(Paragraph("What was found", section_style))
    match_rows: list[list[object]] = [
        [
            text("Measure", table_header_style),
            text("Result", table_header_style),
            text("In plain language", table_header_style),
        ],
        [
            text("Sentences reviewed"),
            text(total_sentences),
            text("Number of extracted sentences included in this report."),
        ],
        [
            text("Sentences with a match"),
            text(f"{matched_sentences} ({sentence_coverage:.2f}%)"),
            text("Sentences for which one or more reference matches were found."),
        ],
        [
            text("No match found"),
            text(max(0, total_sentences - matched_sentences)),
            text("Sentences with no match identified in the available reference collection."),
        ],
        [
            text("Exact matches"),
            text(match_counts.get("exact", 0)),
            text("Sentences containing an exact text match."),
        ],
        [
            text("High / moderate / lower similarity"),
            text(
                f"{match_counts.get('high_similarity', 0)} / "
                f"{match_counts.get('moderate_similarity', 0)} / "
                f"{match_counts.get('low_similarity', 0)}"
            ),
            text("Other matched sentences, grouped by the system's match category."),
        ],
    ]
    story.append(make_table(match_rows, [43 * mm, 39 * mm, 88 * mm], header=True))

    if source_summary:
        story.append(Paragraph("Reference documents with the most matches", section_style))
        source_rows: list[list[object]] = [
            [
                text("Reference document", table_header_style),
                text("Matched sentences", table_header_style),
                text("Average match", table_header_style),
            ]
        ]
        for source in source_summary:
            source_rows.append(
                [
                    text(source["title"]),
                    text(source["matched_sentences"]),
                    text(f'{float(source["average_similarity"]) * 100:.1f}%'),
                ]
            )
        story.append(make_table(source_rows, [94 * mm, 40 * mm, 36 * mm], header=True))
    else:
        story.append(
            text(
                "No reference document matches were recorded for this analysis.",
                body_style,
            )
        )

    story.append(Paragraph("How to understand these results", section_style))
    story.append(
        text(
            "Text similarity: the overall percentage is a text-coverage "
            "measure weighted by match strength. It does not decide whether a "
            "passage is properly cited or constitutes plagiarism.",
        )
    )
    story.append(
        text(
            "AI-writing estimate: when available, this is an experimental "
            "classifier indicator. It can be wrong, especially on technical or "
            "specialist writing, and is not proof of who wrote the document.",
        )
    )
    story.append(
        text(
            "Reference coverage: results depend on the material available "
            "to this installation. A lack of matches does not guarantee that "
            "similar text does not exist elsewhere.",
        )
    )
    story.append(Paragraph("Suggested review steps", section_style))
    for step_number, step in enumerate((
        "Open the detailed scan and read each highlighted passage together "
        "with its reference source.",
        "Check whether a match is a quotation, a citation, common terminology, "
        "or wording that needs to be rewritten and cited.",
        "Use the AI-writing estimate only as a prompt for human review; do not "
        "use it alone to judge a student's work.",
    ), start=1):
        story.append(text(f"{step_number}. {step}"))

    available_algorithms = [
        (label, algorithm_scores.get(key))
        for key, label in (
            ("exact", "Exact phrase comparison"),
            ("ngram", "Phrase-pattern overlap"),
            ("tfidf", "Distinctive word overlap"),
            ("semantic", "Meaning similarity"),
            ("cross_encoder", "Contextual comparison"),
        )
        if algorithm_scores.get(key) is not None
    ]
    if available_algorithms:
        story.append(Paragraph("Supporting comparison signals", section_style))
        story.append(
            text(
                "These are separate comparison signals used during matching; "
                "they are not independent plagiarism percentages and should "
                "not be added together.",
                small_style,
            )
        )
        signal_rows: list[list[object]] = [
            [
                text("Comparison signal", table_header_style),
                text("Strength", table_header_style),
            ]
        ]
        signal_rows.extend(
            [
                [text(label), text(f"{max(0.0, min(1.0, float(value))) * 100:.2f}%")]
                for label, value in available_algorithms
            ]
        )
        story.append(make_table(signal_rows, [125 * mm, 45 * mm], header=True))

    story.extend(
        [
            Spacer(1, 5 * mm),
            text(
                f"Analysis completed on "
                f"{generated_at.astimezone().strftime('%d %B %Y at %H:%M:%S %Z')}. "
                f"AI analysis status: {ai_status.replace('_', ' ').lower()}.",
                small_style,
            ),
            Spacer(1, 2 * mm),
            text(
                "Electronically generated by the ASTE Document Analysis System. "
                "This report supports academic review and does not replace "
                "human assessment.",
                small_style,
            ),
        ]
    )
    document.build(story, onFirstPage=draw_page_footer, onLaterPages=draw_page_footer)


def create_certificate(
    db: Session,
    scan: Scan,
    generated_by,
    student_name_override: str | None = None,
    service_number_override: str | None = None,
    course_override: str | None = None,
    batch_override: str | None = None,
) -> Certificate:

    # --------------------------------------------------------
    # Prevent duplicate certificate for same scan
    # --------------------------------------------------------

    existing = (
        db.query(Certificate)
        .filter(
            Certificate.scan_id == scan.id
        )
        .first()
    )

    if existing:
        return existing

    # --------------------------------------------------------
    # Get latest completed plagiarism analysis
    # --------------------------------------------------------

    analysis = get_latest_completed_analysis(
        db=db,
        scan=scan,
    )

    if not analysis:
        raise ValueError(
            "A completed plagiarism analysis is required "
            "before generating a certificate."
        )

    if analysis.overall_similarity is None:
        raise ValueError(
            "Plagiarism analysis does not contain "
            "an overall plagiarism score."
        )

    # --------------------------------------------------------
    # Determine certificate subject
    # --------------------------------------------------------

    student = scan.owner or scan.scanner

    student_name = (
        student_name_override.strip()
        if student_name_override and student_name_override.strip()
        else student.full_name
    )
    username = student.username

    profile = (
        db.query(StudentOfficerProfile)
        .filter(
            StudentOfficerProfile.user_id
            == student.id
        )
        .first()
    )

    service_number = (
        service_number_override.strip()
        if service_number_override and service_number_override.strip()
        else profile.service_number if profile else None
    )

    course = (
        course_override.strip()
        if course_override and course_override.strip()
        else profile.course if profile else None
    )

    batch = (
        batch_override.strip()
        if batch_override and batch_override.strip()
        else profile.batch if profile else None
    )

    sentence_count = (
        db.query(ScanSentence)
        .filter(ScanSentence.scan_id == scan.id)
        .count()
    )
    match_rows = (
        db.query(PlagiarismMatch)
        .filter(PlagiarismMatch.analysis_id == analysis.id)
        .all()
    )
    match_priority = {
        "LOW_SIMILARITY": 1,
        "MODERATE_SIMILARITY": 2,
        "HIGH_SIMILARITY": 3,
        "EXACT": 4,
    }
    best_match_type_by_sentence: dict[uuid.UUID, str] = {}
    source_sentence_ids: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    source_scores: dict[uuid.UUID, list[float]] = defaultdict(list)

    for match in match_rows:
        match_type = match.detection_method or "LOW_SIMILARITY"
        previous = best_match_type_by_sentence.get(match.scan_sentence_id)
        if previous is None or match_priority.get(match_type, 0) > match_priority.get(previous, 0):
            best_match_type_by_sentence[match.scan_sentence_id] = match_type
        source_sentence_ids[match.reference_document_id].add(match.scan_sentence_id)
        source_scores[match.reference_document_id].append(
            float(match.similarity_score)
        )

    match_counts = {
        "exact": sum(
            match_type == "EXACT"
            for match_type in best_match_type_by_sentence.values()
        ),
        "high_similarity": sum(
            match_type == "HIGH_SIMILARITY"
            for match_type in best_match_type_by_sentence.values()
        ),
        "moderate_similarity": sum(
            match_type == "MODERATE_SIMILARITY"
            for match_type in best_match_type_by_sentence.values()
        ),
        "low_similarity": sum(
            match_type == "LOW_SIMILARITY"
            for match_type in best_match_type_by_sentence.values()
        ),
    }

    reference_documents = (
        db.query(ReferenceDocument)
        .filter(ReferenceDocument.id.in_(source_sentence_ids.keys()))
        .all()
        if source_sentence_ids
        else []
    )
    reference_by_id = {reference.id: reference for reference in reference_documents}
    source_summary = []
    for reference_id, sentence_ids in source_sentence_ids.items():
        reference = reference_by_id.get(reference_id)
        scores = source_scores[reference_id]
        source_summary.append(
            {
                "title": (
                    reference.title
                    if reference
                    else f"Reference {str(reference_id)[:8]}"
                ),
                "matched_sentences": len(sentence_ids),
                "average_similarity": (
                    sum(scores) / len(scores) if scores else 0.0
                ),
            }
        )
    source_summary.sort(
        key=lambda source: (
            int(source["matched_sentences"]),
            float(source["average_similarity"]),
        ),
        reverse=True,
    )

    classifier_result = (
        db.query(AIDetectorResult)
        .join(AIAnalysisRun, AIDetectorResult.run_id == AIAnalysisRun.id)
        .filter(
            AIAnalysisRun.scan_id == scan.id,
            AIDetectorResult.detector_type == "CLASSIFIER",
        )
        .order_by(AIAnalysisRun.created_at.desc())
        .first()
    )
    ai_status = classifier_result.status if classifier_result else "NOT_AVAILABLE"
    ai_score = (
        float(classifier_result.score)
        if classifier_result
        and classifier_result.status == "COMPLETED"
        and classifier_result.score is not None
        else None
    )
    ai_confidence = (
        classifier_model_confidence(classifier_result)
        if classifier_result
        and classifier_result.status == "COMPLETED"
        else None
    )
    algorithm_scores = {
        "exact": (
            float(analysis.exact_match_score)
            if analysis.exact_match_score is not None
            else None
        ),
        "ngram": (
            float(analysis.ngram_score)
            if analysis.ngram_score is not None
            else None
        ),
        "tfidf": (
            float(analysis.tfidf_score)
            if analysis.tfidf_score is not None
            else None
        ),
        "semantic": (
            float(analysis.semantic_score)
            if analysis.semantic_score is not None
            else None
        ),
        "cross_encoder": (
            float(analysis.cross_encoder_score)
            if analysis.cross_encoder_score is not None
            else None
        ),
    }

    # --------------------------------------------------------
    # Generate certificate number
    # --------------------------------------------------------

    certificate_number = (
        generate_certificate_number()
    )

    generated_at = datetime.now(timezone.utc)

    certificate_directory = (
        get_certificate_directory()
    )

    file_name = (
        f"{certificate_number}.pdf"
    )

    certificate_path = (
        certificate_directory / file_name
    )

    # --------------------------------------------------------
    # Generate PDF
    # --------------------------------------------------------

    try:
        generate_certificate_pdf(
            output_path=certificate_path,
            certificate_number=certificate_number,
            scan=scan,
            student_name=student_name,
            username=username,
            service_number=service_number,
            course=course,
            batch=batch,
            plagiarism_score=(
                analysis.overall_similarity
            ),
            ai_score=ai_score,
            ai_confidence=ai_confidence,
            ai_status=ai_status,
            total_sentences=sentence_count,
            matched_sentences=len(best_match_type_by_sentence),
            match_counts=match_counts,
            source_summary=source_summary[:8],
            algorithm_scores=algorithm_scores,
            generated_at=generated_at,
        )

    except Exception:
        if certificate_path.exists():
            certificate_path.unlink()

        raise

    # --------------------------------------------------------
    # Calculate certificate hash
    # --------------------------------------------------------

    certificate_hash = calculate_file_hash(
        certificate_path
    )

    # --------------------------------------------------------
    # Store certificate metadata
    # --------------------------------------------------------

    certificate = Certificate(
        scan_id=scan.id,
        certificate_number=certificate_number,
        certificate_path=str(
            certificate_path
        ),
        generated_at=generated_at,
        generated_by=generated_by.id,
        certificate_hash=certificate_hash,
        status="GENERATED",
    )

    db.add(certificate)
    db.flush()

    return certificate