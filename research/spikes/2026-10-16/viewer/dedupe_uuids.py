"""Give every repeated (uuid "...") in a .kicad_pcb a fresh uuid4 (first occurrence keeps its value)."""
import re
import sys
import uuid

src, dst = sys.argv[1], sys.argv[2]
seen, n = set(), 0


def repl(m):
    global n
    u = m.group(1)
    if u in seen:
        n += 1
        return f'(uuid "{uuid.uuid4()}")'
    seen.add(u)
    return m.group(0)


text = re.sub(r'\(uuid "([0-9a-fA-F-]{36})"\)', repl, open(src).read())
open(dst, "w").write(text)
print(f"replaced {n} duplicate uuids -> {dst}")
