import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import settings
from app.services.embedding_service import _fit_embedding_dimension
from app.services.model_comparison_service import (
    MODEL_DEFINITIONS,
    PUBLISHED_MTEB_RESULTS,
    compare_models,
    get_model_catalog,
)
from app.services.plagiarism_model_service import list_local_embedding_models


class ModelComparisonServiceTests(unittest.TestCase):
    def test_catalog_includes_all_three_local_checkpoints(self):
        catalog = get_model_catalog()

        self.assertEqual(
            [model["name"] for model in catalog],
            [name for name, _ in MODEL_DEFINITIONS],
        )
        self.assertEqual(len(catalog), 3)

        for model in catalog:
            with self.subTest(model=model["name"]):
                self.assertTrue(model["available"])
                self.assertIsNotNone(model["embedding_dimension"])
                self.assertIsNotNone(model["max_sequence_length"])
                self.assertEqual(
                    set(model["mteb"]["categories"]),
                    {
                        "bitext_mining",
                        "classification",
                        "clustering",
                        "pair_classification",
                        "reranking",
                        "retrieval",
                        "sts",
                        "summarization",
                    },
                )

    def test_comparison_runs_every_local_checkpoint(self):
        cases = [
            {
                "text_a": "Technicians inspect the aircraft before maintenance.",
                "text_b": "Before maintenance, the aircraft is checked by technicians.",
                "similar": True,
            },
            {
                "text_a": "The crew completes a checklist before engine startup.",
                "text_b": "The engine should only start after the crew finishes its checklist.",
                "similar": True,
            },
            {
                "text_a": "Technicians inspect the aircraft before maintenance.",
                "text_b": "The garden needs watering during the summer.",
                "similar": False,
            },
            {
                "text_a": "The crew completes a checklist before engine startup.",
                "text_b": "A database index can speed up search queries.",
                "similar": False,
            },
        ]

        report = compare_models(cases, repetitions=1)

        self.assertEqual(
            [result["name"] for result in report["results"]],
            [name for name, _ in MODEL_DEFINITIONS],
        )
        self.assertEqual(set(report["mteb_results"]), set(PUBLISHED_MTEB_RESULTS))
        self.assertEqual(report["case_count"], len(cases))

        for result in report["results"]:
            with self.subTest(model=result["name"]):
                self.assertEqual(result["embedding_dimension"], 768 if result["name"] == "bge-base-en-v1.5" else 1024)
                self.assertEqual(len(result["case_scores"]), len(cases))
                self.assertGreater(result["parameter_count"], 0)
                self.assertGreater(result["texts_per_second"], 0)
                self.assertTrue(0 <= result["quality"]["roc_auc"] <= 1)


class PlagiarismModelServiceTests(unittest.TestCase):
    def _create_model(
        self,
        models_directory: Path,
        name: str,
        dimension: int,
    ) -> None:
        model_directory = models_directory / name
        pooling_directory = model_directory / "1_Pooling"
        pooling_directory.mkdir(parents=True)
        (model_directory / "modules.json").write_text(
            json.dumps(
                [
                    {
                        "type": "sentence_transformers.models.Pooling",
                        "path": "1_Pooling",
                    }
                ]
            ),
            encoding="utf-8",
        )
        (model_directory / "config.json").write_text(
            json.dumps({"hidden_size": dimension}),
            encoding="utf-8",
        )
        (pooling_directory / "config.json").write_text(
            json.dumps({"word_embedding_dimension": dimension}),
            encoding="utf-8",
        )

    def test_discovers_compatible_models_added_to_models_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            models_directory = Path(temporary_directory)
            self._create_model(models_directory, "new-embedding-model", 768)
            self._create_model(models_directory, "too-wide-model", 2048)
            (models_directory / "classifier").mkdir()

            with patch.object(settings, "model_dir", temporary_directory):
                models = list_local_embedding_models()

        self.assertEqual(
            [(model.name, model.embedding_dimension) for model in models],
            [("new-embedding-model", 768)],
        )

    def test_pads_smaller_embeddings_to_database_dimension(self):
        with patch.object(settings, "embedding_dimension", 4):
            self.assertEqual(
                _fit_embedding_dimension([0.6, 0.8]),
                [0.6, 0.8, 0.0, 0.0],
            )

    def test_rejects_embeddings_larger_than_database_dimension(self):
        with patch.object(settings, "embedding_dimension", 2):
            with self.assertRaises(ValueError):
                _fit_embedding_dimension([0.1, 0.2, 0.3])


if __name__ == "__main__":
    unittest.main()
