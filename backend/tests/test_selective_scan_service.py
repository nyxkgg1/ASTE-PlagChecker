from app.services.plagiarism_exclusion_service import remove_excluded_text
from app.services.plagiarism_search_service import compare_lexical_candidate
from app.models.reference import ReferenceSentence
from app.models.scan import ScanSentence
from app.services.document_extraction_service import extract_docx
from docx import Document
from app.services.selective_scan_service import (
    extract_selectable_paragraphs,
    selected_paragraph_text,
)


def test_selectable_paragraphs_default_summary_and_paragraphs_three_four():
    pages = [{
        "page_number": 1,
        "raw_text": (
            "TABLE OF CONTENTS\n"
            "1. INTRODUCTION ........ 1\n"
            "2. AIM ................ 2\n"
            "INDEX\n"
            "aircraft ........ 9\n"
            "SUMMARY\n"
            "This is the report summary.\n"
            "1. INTRODUCTION\n"
            "This introduction is not a numbered report paragraph.\n"
            "3. This is the third report paragraph with enough body text.\n"
            "3.1 Subheading\n"
            "4. This is the fourth report paragraph with enough body text.\n"
        ),
    }]

    selection = extract_selectable_paragraphs(pages)

    assert [item["id"] for item in selection["paragraphs"]] == [
        "summary",
        "paragraph:auto:1",
        "paragraph:3",
        "paragraph:4",
    ]
    assert selection["default_selected_ids"] == [
        "summary",
        "paragraph:3",
        "paragraph:4",
    ]
    assert selection["paragraphs"][1]["text"] == (
        "This introduction is not a numbered report paragraph."
    )
    assert selected_paragraph_text(
        selection,
        ["paragraph:4"],
    ) == {
        1: "This is the fourth report paragraph with enough body text."
    }


def test_excluded_words_and_phrases_are_case_insensitive_and_word_bounded():
    assert remove_excluded_text(
        "REPORTS follow the method of analysis.",
        ["report"],
        ["method of analysis"],
    ) == "REPORTS follow the ."


def test_excluded_terms_do_not_affect_lexical_similarity():
    scan = ScanSentence(
        raw_text="This is a shared technical sentence with special wording.",
        normalized_text="This is a shared technical sentence with special wording.",
    )
    reference = ReferenceSentence(
        normalized_text="This is a shared technical sentence with alternate wording.",
    )

    result = compare_lexical_candidate(
        scan,
        reference,
        excluded_words=["special", "alternate"],
    )

    assert result["exact_score"] == 1.0


def test_unstructured_document_has_selectable_body_paragraphs():
    selection = extract_selectable_paragraphs([{
        "page_number": 1,
        "raw_text": (
            "TITLE\n\n"
            "Body paragraph with enough detail.\n"
            "Parameter\tValue\tUnit\n"
            "Header: INSTR SECRET\n"
            "A second sentence follows the classification header."
        ),
    }])

    assert len(selection["paragraphs"]) == 1
    assert "Body paragraph with enough detail." in selection["paragraphs"][0]["text"]
    assert "A second sentence follows" in selection["paragraphs"][0]["text"]
    assert "INSTR SECRET" not in selection["paragraphs"][0]["text"]
    assert "Parameter" not in selection["paragraphs"][0]["text"]


def test_fter_format_selects_analysis_subparagraphs_and_recommendations():
    pages = [
        {
            "page_number": 1,
            "raw_text": (
                "Header: INSTR SECRET\n"
                "AIRCRAFT & SYSTEMS TESTING ESTABLISHMENT\n"
                "FLIGHT TEST AND EVALUATION REPORT NO AFTPS/xx-xx/12345\n"
                "TOPIC OF REPORT\n"
            ),
        },
        {
            "page_number": 2,
            "raw_text": "Header: INSTR SECRET\nSUMMARY\nThe report summary text.\n",
        },
        {
            "page_number": 3,
            "raw_text": (
                "TABLE OF CONTENTS\n"
                "1. Introduction ........ 8\n"
                "2. Conditions relevant to tests ........ 9\n"
                "3. Analysis and Results ........ 13\n"
            ),
        },
        {
            "page_number": 4,
            "raw_text": "LIST OF APPENDICES (Table)\nAppendix A ........ 26\n",
        },
        {
            "page_number": 5,
            "raw_text": "LIST OF TABLES\nTable 1 ........ 28\n",
        },
        {
            "page_number": 6,
            "raw_text": "LIST OF FIGURES\nFigure 1 ........ 30\n",
        },
        {
            "page_number": 7,
            "raw_text": "INDEX\nAircraft systems ........ 99\n",
        },
        {
            "page_number": 8,
            "raw_text": (
                "Header: INSTR SECRET\n1. Introduction\nThe introduction content.\n"
            ),
        },
        {
            "page_number": 9,
            "raw_text": "2. Conditions relevant to tests\nThe test conditions.\n",
        },
        {
            "page_number": 13,
            "raw_text": (
                "3. Analysis and Results\n"
                "3.1 First analysis subsection\n"
                "Analysis subsection one content.\n"
                "3.2 Second analysis subsection\n"
                "Analysis subsection two content.\n"
            ),
        },
        {
            "page_number": 24,
            "raw_text": "4. Recommendations\nThe recommendation text.\nFooter: INSTR SECRET\n",
        },
    ]

    selection = extract_selectable_paragraphs(pages)

    assert selection["is_fter"] is True
    assert [item["id"] for item in selection["paragraphs"]] == [
        "summary",
        "front:contents",
        "front:appendices",
        "front:tables",
        "front:figures",
        "introduction:1",
        "conditions:1",
        "analysis:3.1",
        "analysis:3.2",
        "recommendations",
    ]
    assert selection["default_selected_ids"] == [
        "summary",
        "analysis:3.1",
        "analysis:3.2",
        "recommendations",
    ]
    assert all(
        "INSTR SECRET" not in item["text"]
        for item in selection["paragraphs"]
    )
    assert all(
        "........" not in item["text"]
        for item in selection["paragraphs"]
    )
    assert all(
        "Aircraft systems" not in item["text"]
        for item in selection["paragraphs"]
    )
    assert all(
        item["id"] not in selection["default_selected_ids"]
        for item in selection["paragraphs"]
        if item["is_front_matter"]
    )
    assert all(
        "First analysis subsection" not in item["text"]
        for item in selection["paragraphs"]
    )


def test_non_fter_document_does_not_receive_fter_preset():
    selection = extract_selectable_paragraphs([{
        "page_number": 1,
        "raw_text": (
            "Project Overview\n"
            "This introduction describes the project.\n"
            "4. Recommendations for the next phase.\n"
        ),
    }])

    assert selection["is_fter"] is False
    assert "front:contents" not in {
        item["id"] for item in selection["paragraphs"]
    }


def test_generic_body_paragraphs_are_grouped_by_nearest_heading():
    selection = extract_selectable_paragraphs([{
        "page_number": 1,
        "raw_text": (
            "Introduction\n\n"
            "The first body paragraph has enough words to be extracted.\n\n"
            "Test Conditions\n\n"
            "A second body paragraph follows the nearest heading."
        ),
    }])

    assert [item["section_title"] for item in selection["paragraphs"]] == [
        "Introduction",
        "Test Conditions",
    ]


def test_fter_default_selects_every_analysis_subparagraph():
    pages = [
        {
            "page_number": 1,
            "raw_text": (
                "AIRCRAFT & SYSTEMS TESTING ESTABLISHMENT\n"
                "CREST\n"
                "FLIGHT TEST AND EVALUATION REPORT NO AFTPS/xx-xx/12345/12345/x\n"
                "SUMMARY\nSummary text.\n"
                "TABLE OF CONTENTS\n"
                "LIST OF APPENDICES\n"
                "LIST OF TABLES\n"
                "LIST OF FIGURES\n"
                "1. Introduction\nIntro text.\n"
                "2. Conditions Relevant to Tests\nConditions text.\n"
                "3. Analysis and Results\n"
                "3.1 First subsection\nFirst analysis text.\n"
                "3.1.1 Nested subsection\nNested analysis text.\n"
                "3.2 Second subsection\nSecond analysis text.\n"
                "4. Recommendations\nRecommendation text.\n"
            ),
        },
        {"page_number": 2, "raw_text": "Header: INSTR SECRET\nFooter: INSTR SECRET\n"},
    ]

    selection = extract_selectable_paragraphs(pages)
    analysis_ids = [
        item["id"]
        for item in selection["paragraphs"]
        if item["section_id"] == "analysis"
    ]

    assert selection["is_fter"] is True
    assert analysis_ids == ["analysis:3.1", "analysis:3.1.1", "analysis:3.2"]
    assert set(analysis_ids).issubset(selection["default_selected_ids"])


def test_docx_headings_are_preserved_for_full_text_and_marked_for_selection(tmp_path):
    path = tmp_path / "report.docx"
    document = Document()
    document.add_paragraph("Custom heading", style="Heading 1")
    document.add_paragraph("3. A numbered body paragraph.")
    document.save(path)

    page = extract_docx(path)[0]

    assert "Custom heading" in page.raw_text
    assert page.heading_lines == ["Custom heading"]
    selection = extract_selectable_paragraphs([{
        "page_number": page.page_number,
        "raw_text": page.raw_text,
        "heading_lines": page.heading_lines,
    }])
    assert all("Custom heading" not in item["text"] for item in selection["paragraphs"])
