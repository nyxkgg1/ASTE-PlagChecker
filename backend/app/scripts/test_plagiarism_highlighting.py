from app.services.plagiarism_highlighting_service import (
    generate_highlighting,
)


scan_text = (
    "Aircraft performance was recorded "
    "using calibrated instrumentation."
)

reference_text = (
    "Aircraft performance was recorded "
    "using calibrated instrumentation "
    "and data gathering equipment."
)


result = generate_highlighting(
    scan_text=scan_text,
    reference_text=reference_text,
)


print("\nHIGHLIGHTING RESULT\n")

print(
    "Character coverage:",
    result[
        "character_coverage_percentage"
    ],
    "%",
)

print("\nSegments:\n")

for segment in result[
    "segments"
]:
    print(
        "MATCHED:"
        if segment["matched"]
        else "UNMATCHED:",
        repr(segment["text"]),
    )