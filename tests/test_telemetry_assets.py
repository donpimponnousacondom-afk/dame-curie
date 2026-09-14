import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cl100k_vocabulary_matches_official_pinned_asset():
    vocabulary = ROOT / "assets/tokenizers/cl100k_base.tiktoken"
    assert hashlib.sha256(vocabulary.read_bytes()).hexdigest() == (
        "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"
    )
    assert len(vocabulary.read_bytes().splitlines()) == 100256
    assert "MIT License" in (vocabulary.parent / "LICENSE").read_text()


def test_tokenizer_dependencies_are_pinned_for_host_and_image():
    host = (ROOT / "requirements.txt").read_text().splitlines()
    image = (ROOT / "docker/requirements.lock").read_text().splitlines()
    for requirement in (
        "tiktoken==0.14.0",
        "regex==2026.9.3",
        "requests==2.34.2",
    ):
        assert requirement in host
        assert requirement in image
