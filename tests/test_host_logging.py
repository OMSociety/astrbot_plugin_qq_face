"""Plugin sources must use the AstrBot host logger."""

from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_LOGGER_PATTERNS = (
    "import logging",
    "logging.getLogger",
)


def test_plugin_sources_use_host_logger() -> None:
    """Plugin modules import logger from astrbot.api, never the standard library."""
    source_files = sorted(
        path
        for path in PLUGIN_ROOT.rglob("*.py")
        if "tests" not in path.relative_to(PLUGIN_ROOT).parts
    )
    assert source_files

    for path in source_files:
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_LOGGER_PATTERNS:
            assert pattern not in text, (
                f"{path.relative_to(PLUGIN_ROOT)} uses {pattern}"
            )
