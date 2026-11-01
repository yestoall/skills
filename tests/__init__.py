# The tests import the skill's scripts straight from its folder: the scripts
# ship with the skill and run with a bare `python3`, so they are not a package.
import sys
from pathlib import Path

SCRIPTS = (
    Path(__file__).resolve().parent.parent
    / "plugins"
    / "nevera"
    / "skills"
    / "nevera-recipes"
    / "scripts"
)
sys.path.insert(0, str(SCRIPTS))
