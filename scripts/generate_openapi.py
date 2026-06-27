"""Programmatic exporter to dump current FastAPI OpenAPI spec to JSON contracts (Phase 6)."""

from __future__ import annotations

import json
import os
import sys

# Ensure backend package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.api.main import app


def generate_openapi() -> None:
    """Generate openapi specification and write to contracts/openapi.json."""
    openapi_schema = app.openapi()

    target_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "contracts")
    )
    os.makedirs(target_dir, exist_ok=True)

    target_file = os.path.join(target_dir, "openapi.json")
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)

    print(f"Successfully generated OpenAPI schema at {target_file}")


if __name__ == "__main__":
    generate_openapi()
