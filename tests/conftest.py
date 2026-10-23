"""
Adds the project root to sys.path so that `from contracts.X import Y` works
when pytest is run from the ai-test-automation/ directory without installing
the package.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# Keep UI run history out of the real runs/ folder while tests run.
import os
import tempfile

os.environ.setdefault("QC_UI_HISTORY", os.path.join(tempfile.mkdtemp(prefix="qc_ui_history_"), "ui_history.jsonl"))
