#!/usr/bin/env python3
"""Criterion-2 memory hog: allocate and touch memory well past the 512 MB
scope cap. Expected fate: SIGKILL by the cgroup OOM killer inside the
scope while the host and its sentinel stay healthy."""
import sys
import time

chunks = []
total = 0
CHUNK = 32 * 1024 * 1024
TARGET = 1536 * 1024 * 1024  # 1.5 GiB, 3x the cap
while total < TARGET:
    b = bytearray(CHUNK)
    for i in range(0, CHUNK, 4096):
        b[i] = 1  # touch every page so it is resident, not virtual
    chunks.append(b)
    total += CHUNK
    print(f"hog: allocated {total // (1024*1024)} MiB", flush=True)
    time.sleep(0.05)
print("hog: SURVIVED to target — CAP DID NOT FIRE", flush=True)
sys.exit(42)
