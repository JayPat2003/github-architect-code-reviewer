"""
types.py — Shared data models for the entire application.

Purpose:
    Centralises all dataclasses and TypedDicts so every module imports
    from one place, preventing circular imports and duplication.

No runtime logic lives here — it is a pure type/schema definition file.
Import order in the pipeline:
    This file is always the FIRST to be imported by every other module.
    Load order: types.py → github_client.py → doc_loader.py
                        → reviewer.py → reporter.py → cli.py
"""

from __future__ import annotations  # enables forward references for all annotations

from dataclasses import dataclass, field
from
