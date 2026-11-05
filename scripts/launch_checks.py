'''Compatibility CLI for the Start BAT:  python scripts/launch_checks.py --check

The implementation lives in backend/launch_checks.py so that it is also packaged in the
installed wheel. This file only makes it runnable from a source checkout.
'''
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend.launch_checks import *  # noqa: E402,F401,F403
from backend.launch_checks import main  # noqa: E402

if __name__ == '__main__':
    sys.exit(main())
