"""The ML engines and model downloads, without loading or fetching a model."""

import io
import math
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from apps.songs import ml
from apps.songs.ml import EngineUnavailable, Label, catalog, get_engine
from apps.songs.ml.keyword import KeywordEngine, stem
from apps.songs.ml.onnx import (
    OnnxEngine,
    entailment_probability,
    label_indices,
    mean_pool,
    unit_length,
)


class KeywordEngineTests(SimpleTestCase):
    engine = KeywordEngine()

    def test_scores_count_distinct_keywords(self):
        label = Label("About grace.", frozenset({"grace", "mercy", "praises"}))
        texts = ["", "Grace, grace!", "Mercy and praise and grace"]
        none, one, three = [self.engine.score(text, [label])[0] for text in texts]
        self.assertEqual(none, 0)
        self.assertAlmostEqual(one, 1 / 3)
        self.assertAlmostEqual(three, 0.6)

    def test_stem_matches_simple_plurals(self):
        self.assertEqual(stem("Praises"), "praise")
        self.assertEqual(stem("God's"), "god")
        self.assertEqual(stem("bless"), "bless")
        self.assertEqual(stem("us"), "us")

    def test_embeddings_are_unit_length_and_similar_for_shared_words(self):
        grace, grace_again, storm = self.engine.embed(
            ["Grace that saves", "saving grace that saves", "the storm at sea"]
        )
        self.assertAlmostEqual(math.sqrt(sum(v * v for v in grace)), 1.0)

        def similarity(a, b):
            return sum(x * y for x, y in zip(a, b))

        self.assertGreater(similarity(grace, grace_again), similarity(grace, storm))

    def test_empty_text_embeds_to_zeros(self):
        self.assertEqual(set(self.engine.embed(["the and of"])[0]), {0.0})


class EngineChoiceTests(SimpleTestCase):
    def tearDown(self):
        ml._engines.clear()

    def test_tests_run_with_the_keyword_engine(self):
        self.assertEqual(get_engine().name, "keyword")
        self.assertIs(get_engine(), get_engine())

    @override_settings(ML_ENGINE="magic")
    def test_unknown_engine(self):
        with self.assertRaisesMessage(EngineUnavailable, "magic"):
            get_engine()

    def test_onnx_engine_without_model_files_explains_what_to_do(self):
        with tempfile.TemporaryDirectory() as folder:
            with override_settings(ML_ENGINE="onnx", ML_MODELS_DIR=Path(folder)):
                with self.assertRaisesMessage(EngineUnavailable, "download_models"):
                    get_engine()


class OnnxMathTests(SimpleTestCase):
    def test_mean_pool_ignores_padding(self):
        hidden = np.array([[[1.0, 2.0], [3.0, 4.0], [100.0, 100.0]]])
        mask = np.array([[1, 1, 0]])
        np.testing.assert_allclose(mean_pool(hidden, mask), [[2.0, 3.0]])

    def test_unit_length(self):
        np.testing.assert_allclose(unit_length(np.array([[3.0, 4.0]])), [[0.6, 0.8]])

    def test_two_way_model(self):
        config = {"id2label": {"0": "entailment", "1": "not_entailment"}}
        self.assertEqual(label_indices(config), (0, None))
        probability = entailment_probability(np.array([[2.0, 0.0]]), 0)
        self.assertAlmostEqual(float(probability[0]), 1 / (1 + math.exp(-2)))

    def test_three_way_model_ignores_neutral(self):
        config = {"id2label": {"0": "contradiction", "1": "neutral", "2": "ENTAILMENT"}}
        entail, contra = label_indices(config)
        self.assertEqual((entail, contra), (2, 0))
        probability = entailment_probability(np.array([[0.0, 50.0, 0.0]]), 2, 0)
        self.assertAlmostEqual(float(probability[0]), 0.5)


def fake_fetch(repo_id, filename, folder):
    path = Path(folder) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{repo_id}:{filename}")
    return str(path)


class DownloadTests(SimpleTestCase):
    def test_saves_the_files_under_fixed_names(self):
        with tempfile.TemporaryDirectory() as folder:
            target = catalog.download(
                catalog.EMBEDDING, folder, fetch=fake_fetch, free_space=10**12
            )
            self.assertEqual(
                sorted(p.name for p in target.iterdir()),
                ["config.json", "model.onnx", "tokenizer.json"],
            )
            self.assertIn(
                "model_quint8_avx2", (target / "model.onnx").read_text("utf-8")
            )
            self.assertTrue(catalog.EMBEDDING.is_installed(folder))
            self.assertFalse(catalog.ZERO_SHOT.is_installed(folder))

    def test_full_model(self):
        with tempfile.TemporaryDirectory() as folder:
            target = catalog.download(
                catalog.ZERO_SHOT,
                folder,
                full=True,
                fetch=fake_fetch,
                free_space=10**12,
            )
            self.assertIn("onnx/model.onnx", (target / "model.onnx").read_text("utf-8"))

    def test_refuses_when_the_disk_is_nearly_full(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesMessage(catalog.DownloadError, "MB free"):
                catalog.download(
                    catalog.EMBEDDING, folder, fetch=fake_fetch, free_space=50 * 2**20
                )

    def test_command_downloads_missing_models_only(self):
        with tempfile.TemporaryDirectory() as folder:
            catalog.download(
                catalog.EMBEDDING, folder, fetch=fake_fetch, free_space=10**12
            )
            downloaded = []

            def download(command, spec, models_dir, *, full):
                downloaded.append((spec.folder, full))
                return Path(models_dir) / spec.folder

            out = io.StringIO()
            with (
                override_settings(ML_MODELS_DIR=Path(folder)),
                mock.patch(
                    "apps.songs.management.commands.download_models.Command.download",
                    download,
                ),
            ):
                call_command("download_models", stdout=out)
            self.assertEqual(downloaded, [(catalog.ZERO_SHOT.folder, False)])
            self.assertIn("already installed", out.getvalue())

    def test_command_reports_a_failed_download(self):
        def fail(command, spec, models_dir, *, full):
            raise catalog.DownloadError("Not enough room.")

        with tempfile.TemporaryDirectory() as folder:
            with (
                override_settings(ML_MODELS_DIR=Path(folder)),
                mock.patch(
                    "apps.songs.management.commands.download_models.Command.download",
                    fail,
                ),
            ):
                with self.assertRaisesMessage(CommandError, "Not enough room."):
                    call_command("download_models", "--full", stdout=io.StringIO())


class OnnxEngineGuardTests(SimpleTestCase):
    def test_lists_the_missing_models(self):
        with tempfile.TemporaryDirectory() as folder:
            catalog.download(
                catalog.EMBEDDING, folder, fetch=fake_fetch, free_space=10**12
            )
            with self.assertRaisesMessage(EngineUnavailable, catalog.ZERO_SHOT.folder):
                OnnxEngine(folder)
