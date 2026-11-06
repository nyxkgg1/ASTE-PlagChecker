from __future__ import annotations

import gc
import json
import math
import statistics
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sentence_transformers import SentenceTransformer


MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
MODEL_DEFINITIONS = (
    ("Qwen3-0.6B-Base", "Qwen3-0.6B-Base"),
    ("bge-large-en-v1.5", "bge-large-en-v1.5"),
    ("bge-base-en-v1.5", "bge-base-en-v1.5"),
)

PUBLISHED_MTEB_RESULTS: dict[str, dict[str, Any]] = {
    "Qwen3-0.6B-Base": {
        "model_name": "Qwen3-Embedding-0.6B",
        "benchmark": "MTEB English v2",
        "overall_task_score": 70.70,
        "mean_type_score": 64.88,
        "score_kind": "reported",
        "task_count": None,
        "categories": {
            "bitext_mining": None,
            "classification": 85.76,
            "clustering": 54.05,
            "pair_classification": 84.37,
            "reranking": 48.18,
            "retrieval": 61.83,
            "sts": 86.57,
            "summarization": 33.43,
        },
        "source_url": (
            "https://huggingface.co/Qwen/Qwen3-Embedding-0.6B"
        ),
        "score_method": (
            "Official MTEB English v2 model-card Mean(Task) and category "
            "scores. The mean task score weights benchmark tasks equally."
        ),
    },
    "bge-large-en-v1.5": {
        "model_name": "bge-large-en-v1.5",
        "benchmark": "MTEB English (bundled model-card task set)",
        "overall_task_score": 60.35,
        "mean_type_score": 61.84,
        "score_kind": "derived_from_model_card",
        "task_count": 68,
        "categories": {
            "bitext_mining": None,
            "classification": 75.97,
            "clustering": 46.09,
            "pair_classification": 87.12,
            "reranking": 60.03,
            "retrieval": 48.93,
            "sts": 83.11,
            "summarization": 31.61,
        },
        "source_url": (
            "https://huggingface.co/BAAI/bge-large-en-v1.5"
        ),
        "score_method": (
            "Derived as the unweighted mean of 68 bundled model-card task "
            "scores using each MTEB task's primary metric; Mean(Type) is "
            "the unweighted mean of available category means. The model "
            "card does not publish an aggregate score."
        ),
    },
    "bge-base-en-v1.5": {
        "model_name": "bge-base-en-v1.5",
        "benchmark": "MTEB English (bundled model-card task set)",
        "overall_task_score": 59.81,
        "mean_type_score": 61.23,
        "score_kind": "derived_from_model_card",
        "task_count": 68,
        "categories": {
            "bitext_mining": None,
            "classification": 75.53,
            "clustering": 45.77,
            "pair_classification": 86.55,
            "reranking": 58.86,
            "retrieval": 48.41,
            "sts": 82.40,
            "summarization": 31.07,
        },
        "source_url": "https://huggingface.co/BAAI/bge-base-en-v1.5",
        "score_method": (
            "Derived as the unweighted mean of 68 bundled model-card task "
            "scores using each MTEB task's primary metric; Mean(Type) is "
            "the unweighted mean of available category means. The model "
            "card does not publish an aggregate score."
        ),
    },
}

_comparison_lock = threading.Lock()


def _model_path(folder: str) -> Path:
    return MODELS_DIR / folder


def _directory_size(path: Path) -> int:
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def get_model_catalog() -> list[dict[str, Any]]:
    catalog = []

    for name, folder in MODEL_DEFINITIONS:
        path = _model_path(folder)
        config_path = path / "config.json"
        pooling_config_path = path / "1_Pooling" / "config.json"
        sentence_config_path = path / "sentence_bert_config.json"

        model: dict[str, Any] = {
            "name": name,
            "available": path.is_dir() and config_path.is_file(),
            "checkpoint_size_bytes": (
                _directory_size(path) if path.is_dir() else None
            ),
            "embedding_dimension": None,
            "max_sequence_length": None,
            "architecture": None,
            "layers": None,
            "hidden_size": None,
            "attention_heads": None,
            "key_value_heads": None,
            "intermediate_size": None,
            "vocabulary_size": None,
            "max_position_embeddings": None,
            "configured_dtype": None,
            "pooling": None,
            "mteb": PUBLISHED_MTEB_RESULTS[name],
        }

        if not model["available"]:
            catalog.append(model)
            continue

        with config_path.open(encoding="utf-8") as file:
            config = json.load(file)

        model["architecture"] = config.get("model_type")
        model["layers"] = config.get("num_hidden_layers")
        model["hidden_size"] = config.get("hidden_size")
        model["attention_heads"] = config.get("num_attention_heads")
        model["key_value_heads"] = config.get("num_key_value_heads")
        model["intermediate_size"] = config.get("intermediate_size")
        model["vocabulary_size"] = config.get("vocab_size")
        model["max_position_embeddings"] = config.get(
            "max_position_embeddings"
        )
        model["configured_dtype"] = config.get("torch_dtype")

        if pooling_config_path.is_file():
            with pooling_config_path.open(encoding="utf-8") as file:
                pooling = json.load(file)
            model["embedding_dimension"] = pooling.get(
                "word_embedding_dimension"
            )
            enabled_modes = [
                name.removeprefix("pooling_mode_").removesuffix("_tokens")
                for name, enabled in pooling.items()
                if name.startswith("pooling_mode_") and enabled
            ]
            model["pooling"] = ", ".join(enabled_modes) or "configured"

        if sentence_config_path.is_file():
            with sentence_config_path.open(encoding="utf-8") as file:
                sentence_config = json.load(file)
            model["max_sequence_length"] = sentence_config.get(
                "max_seq_length"
            )

        if model["max_sequence_length"] is None:
            model["max_sequence_length"] = config.get(
                "max_position_embeddings"
            )
        if model["embedding_dimension"] is None:
            model["embedding_dimension"] = config.get("hidden_size")

        catalog.append(model)

    return catalog


def _binary_metrics(
    labels: list[bool],
    scores: list[float],
    threshold: float,
) -> dict[str, float | int]:
    true_positive = false_positive = true_negative = false_negative = 0

    for label, score in zip(labels, scores, strict=True):
        predicted = score >= threshold
        if predicted and label:
            true_positive += 1
        elif predicted:
            false_positive += 1
        elif label:
            false_negative += 1
        else:
            true_negative += 1

    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 0.0
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    accuracy = (true_positive + true_negative) / len(labels)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "true_negative": true_negative,
        "false_negative": false_negative,
    }


def _roc_auc(labels: list[bool], scores: list[float]) -> float:
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        raise ValueError("ROC AUC requires both positive and negative examples.")

    ordered = sorted(zip(scores, labels, strict=True), key=lambda item: item[0])
    positive_rank_sum = 0.0
    index = 0

    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = ((index + 1) + end) / 2
        positive_rank_sum += average_rank * sum(
            label for _, label in ordered[index:end]
        )
        index = end

    return (
        positive_rank_sum - positives * (positives + 1) / 2
    ) / (positives * negatives)


def _quality_metrics(
    labels: list[bool],
    scores: list[float],
) -> dict[str, Any]:
    fixed_threshold = _binary_metrics(labels, scores, 0.5)
    candidates = sorted(set(scores))
    best_threshold = candidates[0]
    best_metrics = _binary_metrics(labels, scores, best_threshold)

    for threshold in candidates[1:]:
        metrics = _binary_metrics(labels, scores, threshold)
        if metrics["f1"] > best_metrics["f1"]:
            best_threshold = threshold
            best_metrics = metrics

    positive_scores = [
        score for label, score in zip(labels, scores, strict=True) if label
    ]
    negative_scores = [
        score for label, score in zip(labels, scores, strict=True) if not label
    ]

    return {
        "roc_auc": _roc_auc(labels, scores),
        "accuracy_at_0_5": fixed_threshold["accuracy"],
        "precision_at_0_5": fixed_threshold["precision"],
        "recall_at_0_5": fixed_threshold["recall"],
        "f1_at_0_5": fixed_threshold["f1"],
        "best_threshold": best_threshold,
        "best_f1": best_metrics["f1"],
        "positive_mean_similarity": statistics.mean(positive_scores),
        "negative_mean_similarity": statistics.mean(negative_scores),
        "similarity_margin": (
            statistics.mean(positive_scores) - statistics.mean(negative_scores)
        ),
        "confusion_at_0_5": {
            key: fixed_threshold[key]
            for key in (
                "true_positive",
                "false_positive",
                "true_negative",
                "false_negative",
            )
        },
    }


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (
        position - lower
    )


def _evaluate_model(
    name: str,
    folder: str,
    cases: list[dict[str, Any]],
    repetitions: int,
) -> dict[str, Any]:
    path = _model_path(folder)
    if not path.is_dir():
        raise FileNotFoundError(f"Local model directory not found: {path}")

    texts = list(
        dict.fromkeys(
            text
            for case in cases
            for text in (case["text_a"], case["text_b"])
        )
    )
    labels = [case["similar"] for case in cases]

    load_start = time.perf_counter()
    model = SentenceTransformer(
        str(path),
        local_files_only=True,
        device="cpu",
    )
    load_seconds = time.perf_counter() - load_start

    try:
        max_sequence_length = int(model.max_seq_length)
        tokenized = model.tokenizer(
            texts,
            add_special_tokens=True,
            truncation=False,
            padding=False,
        )
        token_lengths = [len(ids) for ids in tokenized["input_ids"]]
        token_lengths.sort()
        truncated_text_count = sum(
            length > max_sequence_length for length in token_lengths
        )

        model.encode(
            texts[: min(len(texts), 2)],
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        durations = []
        embeddings = None
        for _ in range(repetitions):
            started = time.perf_counter()
            embeddings = model.encode(
                texts,
                batch_size=32,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            durations.append(time.perf_counter() - started)

        if embeddings is None:
            raise RuntimeError("Embedding benchmark did not produce results.")

        vectors = np.asarray(embeddings, dtype=np.float32)
        if not np.isfinite(vectors).all():
            raise ValueError(f"{name} produced non-finite embedding values.")

        norms = np.linalg.norm(vectors, axis=1)
        text_index = {text: index for index, text in enumerate(texts)}
        scores = [
            float(
                np.dot(
                    vectors[text_index[case["text_a"]]],
                    vectors[text_index[case["text_b"]]],
                )
            )
            for case in cases
        ]

        median_seconds = statistics.median(durations)
        total_parameters = sum(
            parameter.numel() for parameter in model.parameters()
        )
        parameter_memory_bytes = sum(
            parameter.numel() * parameter.element_size()
            for parameter in model.parameters()
        )

        return {
            "name": name,
            "checkpoint_size_bytes": _directory_size(path),
            "parameter_count": total_parameters,
            "parameter_memory_bytes": parameter_memory_bytes,
            "inference_dtype": str(next(model.parameters()).dtype).removeprefix(
                "torch."
            ),
            "embedding_dimension": int(vectors.shape[1]),
            "max_sequence_length": max_sequence_length,
            "architecture": type(model[0].auto_model.config).__name__,
            "pooling": type(model[1]).__name__ if len(model) > 1 else "unknown",
            "load_seconds": load_seconds,
            "benchmark_repetitions": repetitions,
            "unique_text_count": len(texts),
            "median_batch_seconds": median_seconds,
            "p95_batch_seconds": _percentile(durations, 0.95),
            "batch_latency_stddev_seconds": (
                statistics.pstdev(durations) if len(durations) > 1 else 0.0
            ),
            "median_ms_per_text": median_seconds * 1000 / len(texts),
            "texts_per_second": len(texts) / median_seconds,
            "pair_scores_per_second": len(cases) / median_seconds,
            "mean_embedding_norm": float(np.mean(norms)),
            "min_embedding_norm": float(np.min(norms)),
            "max_embedding_norm": float(np.max(norms)),
            "truncated_text_count": truncated_text_count,
            "truncated_text_percent": (
                100 * truncated_text_count / len(texts)
            ),
            "mean_input_tokens": statistics.mean(token_lengths),
            "p95_input_tokens": _percentile(
                [float(length) for length in token_lengths], 0.95
            ),
            "max_input_tokens": max(token_lengths),
            "quality": _quality_metrics(labels, scores),
            "case_scores": [
                {
                    "similar": case["similar"],
                    "similarity": score,
                    "text_a": case["text_a"],
                    "text_b": case["text_b"],
                }
                for case, score in zip(cases, scores, strict=True)
            ],
        }
    finally:
        del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def compare_models(
    cases: list[dict[str, Any]],
    repetitions: int = 3,
) -> dict[str, Any]:
    with _comparison_lock:
        results = [
            _evaluate_model(name, folder, cases, repetitions)
            for name, folder in MODEL_DEFINITIONS
        ]

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "device": "CPU",
        "case_count": len(cases),
        "positive_case_count": sum(case["similar"] for case in cases),
        "negative_case_count": sum(not case["similar"] for case in cases),
        "mteb_results": PUBLISHED_MTEB_RESULTS,
        "results": results,
    }
