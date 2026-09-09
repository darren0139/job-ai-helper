from __future__ import annotations

import os
from pathlib import Path

from database import tailoring_version_manager as base_manager

database_path = os.environ.get("PHASE9D_TEST_DATABASE")
if database_path:
    base_manager.DB_PATH = Path(database_path)

from tailoring.blueprint_tag_library_ui import render_blueprint_tag_library

render_blueprint_tag_library()
