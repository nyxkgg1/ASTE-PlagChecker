import argparse
from pathlib import Path

from sentence_transformers import SentenceTransformer, util


MODELS_DIR = Path(__file__).resolve().parent
MODEL_PATHS = (
    ("Qwen3-0.6B-Base", MODELS_DIR / "Qwen3-0.6B-Base"),
    ("bge-large-en-v1.5", MODELS_DIR / "bge-large-en-v1.5"),
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare cosine similarity for the same reference and test text "
            "using the local Qwen3 and BGE embedding models."
        )
    )
    parser.add_argument(
        "--reference",
        required=True,
        help="Reference/source text to compare against.",
    )
    parser.add_argument(
        "--test",
        required=True,
        help="Test/submitted text to compare against the reference.",
    )
    args = parser.parse_args()

    if not args.reference.strip() or not args.test.strip():
        parser.error("--reference and --test must not be empty.")

    print("Cosine similarity for the same reference/test pair:")
    for name, model_path in MODEL_PATHS:
        if not model_path.is_dir():
            raise FileNotFoundError(
                f"Local model directory for {name} not found: {model_path}"
            )

        print(f"\nLoading {name} from {model_path}...")
        model = SentenceTransformer(str(model_path), local_files_only=True)
        embeddings = model.encode(
            [args.reference, args.test],
            convert_to_tensor=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        score = util.cos_sim(embeddings[0], embeddings[1]).item()
        print(f"{name}: {score:.6f}")
        del model

    print(
        "\nCosine similarity scores are model-specific; use labeled examples "
        "to choose a plagiarism threshold."
    )


if __name__ == "__main__":
    main()
