from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


CLASSIFIER_MODEL_NAME = "rasbt/ai-text-detector-modernbert"
CLASSIFIER_MODEL_VERSION = "a6efd4bf6ecd852f332b2569ae0f98cae13b7985"
CLASSIFIER_MAX_LENGTH = 8192
CLASSIFIER_OVERLAP_TOKENS = 128
SENTENCE_HIGHLIGHT_THRESHOLD = 0.8

_inference_lock = Lock()


class AIAuthorshipClassifierError(Exception):
    """Raised when the local authorship classifier cannot process text."""


@lru_cache(maxsize=2)
def _load_classifier(
    model_path: str,
) -> tuple[Any, Any, torch.device, dict[str, Any]]:
    path = Path(model_path)
    if not path.is_dir():
        raise FileNotFoundError(
            f"AI classifier model directory was not found: {path}"
        )

    metadata_path = path / "detector-config.json"
    if not metadata_path.is_file():
        raise AIAuthorshipClassifierError(
            "The classifier detector-config.json file is missing."
        )

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AIAuthorshipClassifierError(
            "The classifier metadata could not be read."
        ) from exc

    if not isinstance(metadata, dict):
        raise AIAuthorshipClassifierError(
            "The classifier metadata must be a JSON object."
        )

    label_mapping = metadata.get("label_mapping")
    if not isinstance(label_mapping, dict):
        raise AIAuthorshipClassifierError(
            "The classifier has no valid label mapping."
        )

    ai_label = label_mapping.get("ai")
    temperature = metadata.get("temperature")
    max_length = metadata.get("max_length")
    if (
        isinstance(ai_label, bool)
        or not isinstance(ai_label, int)
        or isinstance(temperature, bool)
        or not isinstance(temperature, (int, float))
        or not math.isfinite(temperature)
        or temperature <= 0
        or isinstance(max_length, bool)
        or not isinstance(max_length, int)
        or max_length < 8
        or max_length > CLASSIFIER_MAX_LENGTH
    ):
        raise AIAuthorshipClassifierError(
            "The classifier label mapping or inference configuration is invalid."
        )

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            path,
            local_files_only=True,
            use_fast=True,
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            path,
            local_files_only=True,
            dtype=torch.float32,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        raise AIAuthorshipClassifierError(
            "The local classifier model could not be loaded."
        ) from exc

    if ai_label >= model.config.num_labels:
        raise AIAuthorshipClassifierError(
            "The AI label index is outside the classifier output range."
        )

    if tokenizer.is_fast is not True:
        raise AIAuthorshipClassifierError(
            "The classifier requires a fast tokenizer for full-document chunking."
        )

    device_name = (
        "cuda"
        if torch.cuda.is_available()
        else "mps"
        if torch.backends.mps.is_available()
        else "cpu"
    )
    device = torch.device(device_name)
    model.to(device)
    model.eval()

    return tokenizer, model, device, metadata


def classify_document(
    text: str,
    *,
    model_path: str,
) -> dict[str, Any]:
    """Score all document tokens using the locally registered classifier."""
    if not isinstance(text, str) or not text.strip():
        raise AIAuthorshipClassifierError(
            "No usable document text was available for classification."
        )

    tokenizer, model, device, metadata = _load_classifier(model_path)
    max_length = metadata["max_length"]
    stride = min(CLASSIFIER_OVERLAP_TOKENS, max_length // 4)

    try:
        encoded = tokenizer(
            text,
            truncation=True,
            max_length=max_length,
            stride=stride,
            padding=True,
            return_overflowing_tokens=True,
            return_tensors="pt",
        )
        input_ids = encoded["input_ids"]
        attention_mask = encoded["attention_mask"]
    except (ValueError, RuntimeError) as exc:
        raise AIAuthorshipClassifierError(
            "The document could not be tokenized by the classifier."
        ) from exc

    chunk_count = input_ids.shape[0]
    if chunk_count == 0:
        raise AIAuthorshipClassifierError(
            "The classifier tokenizer produced no input chunks."
        )

    ai_index = metadata["label_mapping"]["ai"]
    temperature = float(metadata["temperature"])
    weighted_probability = 0.0
    total_weight = 0
    total_tokens = 0

    try:
        with _inference_lock, torch.inference_mode():
            for index in range(chunk_count):
                chunk_ids = input_ids[index:index + 1].to(device)
                chunk_mask = attention_mask[index:index + 1].to(device)
                chunk_token_count = int(chunk_mask.sum().item())
                content_token_count = max(
                    1,
                    chunk_token_count
                    - tokenizer.num_special_tokens_to_add(pair=False),
                )
                token_weight = max(
                    1,
                    content_token_count - (stride if index > 0 else 0),
                )

                logits = model(
                    input_ids=chunk_ids,
                    attention_mask=chunk_mask,
                ).logits
                probability = (
                    torch.softmax(logits.float() / temperature, dim=-1)[
                        0, ai_index
                    ]
                    .item()
                )

                if not math.isfinite(probability):
                    raise AIAuthorshipClassifierError(
                        "The classifier returned a non-finite probability."
                    )

                weighted_probability += probability * token_weight
                total_weight += token_weight
                total_tokens += token_weight
    except AIAuthorshipClassifierError:
        raise
    except (RuntimeError, ValueError) as exc:
        raise AIAuthorshipClassifierError(
            "The classifier inference failed."
        ) from exc

    probability = weighted_probability / total_weight
    return {
        "ai_probability": probability,
        "chunk_count": chunk_count,
        "token_count": total_tokens,
        "max_length": max_length,
        "overlap_tokens": stride,
        "aggregation": "TOKEN_WEIGHTED_MEAN_OF_OVERLAPPING_CHUNKS",
        "calibration_temperature": temperature,
        "device": str(device),
    }


def classify_sentences(
    sentences: list[str],
    *,
    model_path: str,
) -> list[float]:
    """Return AI-class softmax outputs for individual document sentences."""
    if not sentences:
        return []

    tokenizer, model, device, metadata = _load_classifier(model_path)
    ai_index = metadata["label_mapping"]["ai"]
    temperature = float(metadata["temperature"])
    max_length = metadata["max_length"]
    probabilities: list[float] = []

    try:
        with _inference_lock, torch.inference_mode():
            for start in range(0, len(sentences), 8):
                batch = sentences[start:start + 8]
                encoded = tokenizer(
                    batch,
                    truncation=True,
                    max_length=max_length,
                    padding=True,
                    return_tensors="pt",
                )
                logits = model(
                    input_ids=encoded["input_ids"].to(device),
                    attention_mask=encoded["attention_mask"].to(device),
                ).logits
                batch_probabilities = torch.softmax(
                    logits.float() / temperature,
                    dim=-1,
                )[:, ai_index].tolist()
                if any(not math.isfinite(value) for value in batch_probabilities):
                    raise AIAuthorshipClassifierError(
                        "The classifier returned a non-finite sentence probability."
                    )
                probabilities.extend(float(value) for value in batch_probabilities)
    except AIAuthorshipClassifierError:
        raise
    except (RuntimeError, ValueError) as exc:
        raise AIAuthorshipClassifierError(
            "The classifier could not score individual document sentences."
        ) from exc

    return probabilities
