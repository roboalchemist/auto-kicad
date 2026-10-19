"""Inspect a GLB: header, JSON chunk, node tree, meshes, materials (stdlib only)."""
import json
import struct
import sys
from collections import Counter


def load(path):
    data = open(path, "rb").read()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF", magic
    clen, ctype = struct.unpack_from("<I4s", data, 12)
    assert ctype == b"JSON", ctype
    gltf = json.loads(data[20:20 + clen])
    return version, length, gltf


def main(path, verbose=True):
    version, length, g = load(path)
    nodes, meshes, mats = g.get("nodes", []), g.get("meshes", []), g.get("materials", [])
    print(f"== {path}: glTF v{version}, {length} bytes, nodes={len(nodes)} meshes={len(meshes)} "
          f"materials={len(mats)} accessors={len(g.get('accessors', []))} extras={'extras' in g}")
    print("asset:", g.get("asset"), "scenes:", [s.get("name") for s in g.get("scenes", [])])
    child = {c for n in nodes for c in n.get("children", [])}
    roots = [i for i in range(len(nodes)) if i not in child]

    def walk(i, depth):
        n = nodes[i]
        m = n.get("mesh")
        mdesc = ""
        if m is not None:
            mm = meshes[m]
            prims = mm.get("primitives", [])
            mnames = [mats[p["material"]].get("name") if "material" in p else None for p in prims]
            mdesc = f" mesh#{m} '{mm.get('name')}' prims={len(prims)} mats={Counter(mnames).most_common()}"
        extra = {k: v for k, v in n.items() if k in ("extras", "translation", "rotation", "scale", "matrix")}
        if verbose or depth < 3:
            print("  " * depth + f"- node#{i} '{n.get('name')}'{mdesc} {json.dumps(extra) if extra else ''}")
        for c in n.get("children", []):
            walk(c, depth + 1)

    for r in roots:
        walk(r, 0)
    print("materials:", [(m.get("name"), m.get("pbrMetallicRoughness", {}).get("baseColorFactor")) for m in mats])
    print("mesh names:", Counter(m.get("name") for m in meshes).most_common(40))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p, verbose="--quiet" not in sys.argv)
