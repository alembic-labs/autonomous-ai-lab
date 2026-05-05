"""Quick GLB inspector — dumps JSON header so we can see animations + bones."""

import json
import struct
import sys
from pathlib import Path


def inspect(path: Path) -> dict:
    with path.open("rb") as f:
        magic, version, _length = struct.unpack("<III", f.read(12))
        if magic != 0x46546C67:
            raise ValueError(f"Not a GLB: {path}")
        chunk_len, chunk_type = struct.unpack("<II", f.read(8))
        if chunk_type != 0x4E4F534A:
            raise ValueError(f"First chunk is not JSON in {path}")
        return json.loads(f.read(chunk_len))


def summarise(path: Path) -> None:
    data = inspect(path)
    nodes = data.get("nodes", [])
    skins = data.get("skins", [])
    anims = data.get("animations", [])
    print(f"=== {path.name} ===")
    print(f"  nodes: {len(nodes)}, skins: {len(skins)}, animations: {len(anims)}")
    for s in skins:
        joints = s.get("joints", [])
        print(f"  skin joints: {len(joints)}")
    for i, a in enumerate(anims):
        chans = a.get("channels", [])
        print(f"  anim[{i}] name={a.get('name')!r} channels={len(chans)}")
        # Map channels back to node names for readability.
        target_nodes: list[str] = []
        for c in chans[:6]:
            tgt = c.get("target", {})
            node_idx = tgt.get("node")
            if node_idx is None:
                continue
            nname = nodes[node_idx].get("name", f"<node {node_idx}>") if node_idx < len(nodes) else f"<oob {node_idx}>"
            target_nodes.append(f"{nname}.{tgt.get('path')}")
        print(f"    sample channels: {target_nodes}")
    # First few node names — useful to compare base vs anim GLB bone naming.
    sample = [n.get("name", "") for n in nodes[:12]]
    print(f"  sample node names: {sample}")
    print()


if __name__ == "__main__":
    paths = [Path(p) for p in sys.argv[1:]]
    for p in paths:
        try:
            summarise(p)
        except Exception as err:  # noqa: BLE001
            print(f"!! {p}: {err}")
