"""Generate the machine-readable production curriculum coverage manifest."""
from __future__ import annotations

import json
from pathlib import Path

from api.services.curriculum.curriculum_release import audit_curriculum_coverage


def main() -> None:
    manifest = audit_curriculum_coverage()
    output = Path(__file__).resolve().parents[1] / "data" / "curriculum_release_coverage.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output}: {manifest['supported_lessons']} supported, {manifest['missing_lessons']} missing")


if __name__ == "__main__":
    main()
