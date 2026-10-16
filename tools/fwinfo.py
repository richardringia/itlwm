#!/usr/bin/env python3
"""Dump capabilities / API flags / command versions from an iwlwifi .ucode file."""
import struct, sys
d = open(sys.argv[1], 'rb').read()
assert struct.unpack_from('<I', d, 4)[0] == 0x0a4c5749, 'bad magic'
print('name:', d[8:72].split(b'\0')[0].decode())
off = 8 + 64 + 4 + 4 + 8
capa, api, cmds = set(), set(), []
while off + 8 <= len(d):
    t, l = struct.unpack_from('<II', d, off); off += 8
    v = d[off:off + l]; off += (l + 3) & ~3
    if t in (29, 30):
        idx, bits = struct.unpack_from('<II', v)
        s = api if t == 29 else capa
        for b in range(32):
            if bits >> b & 1: s.add(idx * 32 + b)
    elif t == 48:
        for i in range(0, l, 4):
            cmds.append(tuple(v[i:i + 4]))
print('capa:', sorted(capa))
print('api :', sorted(api))
for c, g, cv, nv in sorted(cmds, key=lambda x: (x[1], x[0])):
    print(f'grp {g:#04x} cmd {c:#04x}  cmd_ver {cv:3d}  notif_ver {nv:3d}')
