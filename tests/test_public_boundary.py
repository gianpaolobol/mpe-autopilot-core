from pathlib import Path

FORBIDDEN = (
    "motore-pratiche-edilizie",
    "speculative/v0.13-v0.22",
    "runtime/autopilot-state",
    "C:\\MPE_AUTOPILOT",
    "OPENAI_API_KEY",
    "MPE_REPO_TOKEN",
    "qwen2.5-coder",
    "ULTRA_TINY",
)

SCAN_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".txt"}


def test_public_repository_contains_no_private_product_markers():
    root = Path(__file__).resolve().parents[1]
    findings = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        if ".git" in path.parts or ".pytest_cache" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in FORBIDDEN:
            if marker in text and path.name != "test_public_boundary.py":
                findings.append((str(path.relative_to(root)), marker))
    assert findings == []
