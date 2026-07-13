"""Pre-seed the index with bundled sample documents on first boot."""
import logging
import os

from .config import get_settings
from .rag.index import document_exists, ingest_file

logger = logging.getLogger("seed")


def seed_samples() -> None:
    s = get_settings()
    if not s.seed_samples:
        return
    if not os.path.isdir(s.samples_dir):
        logger.warning("Samples dir %s not found; skipping seed.", s.samples_dir)
        return

    for name in sorted(os.listdir(s.samples_dir)):
        path = os.path.join(s.samples_dir, name)
        if not os.path.isfile(path):
            continue
        if document_exists(name):
            continue
        try:
            n = ingest_file(path, name)
            logger.info("Seeded sample '%s' (%d chunks)", name, n)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to seed sample '%s': %s", name, exc)
