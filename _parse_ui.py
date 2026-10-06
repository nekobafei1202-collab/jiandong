import re
import sys
from pathlib import Path

p = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
pkgs = sorted(set(re.findall(r'package="([^"]+)"', p)))
print("packages:", pkgs[:20])
texts = [t for t in re.findall(r'text="([^"]{1,80})"', p) if t.strip()]
print("texts:", texts[:50])
print("has_jiandong", "jiandong" in p)
print("has_keyguard", "keyguard" in p)
