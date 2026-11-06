from pathlib import Path

from sentence_transformers import SentenceTransformer


MODEL_PATH = Path(__file__).resolve().parent / "Qwen3-0.6B-Base"

if not MODEL_PATH.is_dir():
    raise FileNotFoundError(
        f"Local Qwen3 model directory not found: {MODEL_PATH}"
    )

model = SentenceTransformer(str(MODEL_PATH), local_files_only=True)

print("Model:", MODEL_PATH)
print("Embedding dimension:", model.get_embedding_dimension())