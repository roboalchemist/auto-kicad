"""Viewer shim: rewrite KiCad 10 name-only nets `(net "X")` into numbered `(net N "X")` + a net table,
so KiCanvas (which only understands numbered nets) gets net names. Display-only; never feed back to KiCad."""
import re
import sys

src, dst = sys.argv[1], sys.argv[2]
text = open(src).read()
names = []
for m in re.finditer(r'\(net "((?:[^"\\]|\\.)*)"\)', text):
    if m.group(1) not in names:
        names.append(m.group(1))
num = {n: i + 1 for i, n in enumerate(names)}
text = re.sub(r'\(net "((?:[^"\\]|\\.)*)"\)', lambda m: f'(net {num[m.group(1)]} "{m.group(1)}")', text)
table = '\t(net 0 "")\n' + "".join(f'\t(net {i} "{n}")\n' for n, i in num.items())
text = re.sub(r"(\n\t\(setup\b)", "\n" + table.rstrip("\n") + r"\1", text, count=1)
open(dst, "w").write(text)
print(f"{len(names)} nets numbered -> {dst}")
