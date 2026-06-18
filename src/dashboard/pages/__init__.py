from __future__ import annotations
import sys, os
for _p in ['/mount/src/swing-platform', os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))]:
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

