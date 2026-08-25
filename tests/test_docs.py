from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_required_documentation_files_exist():
    files = [
        PROJECT_ROOT / "docs" / "internal" / "README.md",
        PROJECT_ROOT / "docs" / "internal" / "CHANGELOG.md",
        PROJECT_ROOT / "docs" / "internal" / "FINDINGS.md",
        PROJECT_ROOT / "docs" / "internal" / "INCIDENTS.md",
        PROJECT_ROOT / "docs" / "internal" / "COMPATIBILITY.md",
        PROJECT_ROOT / "docs" / "ai" / "SYSTEM_CONTEXT.md",
        PROJECT_ROOT / "docs" / "ai" / "ACTIVE_ISSUES.md",
        PROJECT_ROOT / "docs" / "ai" / "RESOLVED_ISSUES.md",
        PROJECT_ROOT / "docs" / "ai" / "ARCHITECTURE.md",
        PROJECT_ROOT / "docs" / "ai" / "TROUBLESHOOTING_HISTORY.md",
        PROJECT_ROOT / "docs" / "public" / "README.md",
        PROJECT_ROOT / "docs" / "public" / "CAPABILITIES.md",
        PROJECT_ROOT / "docs" / "public" / "SUPPORTED_APPS.md",
        PROJECT_ROOT / "docs" / "public" / "KNOWN_ISSUES.md",
        PROJECT_ROOT / "docs" / "public" / "ROADMAP.md",
    ]

    for file_path in files:
        assert file_path.exists(), f"Missing required file: {file_path}"
