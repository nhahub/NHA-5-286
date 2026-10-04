"""
Adds the project root to sys.path so that `from contracts.X import Y` works
when pytest is run from the ai-test-automation/ directory without installing
the package.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
