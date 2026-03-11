#!/usr/bin/env python3
"""Debug script to check full LXD API response for VMs"""

import sys
import json
from pylxd import Client

client = Client()

# Get test1 instance
inst = client.instances.get('test1')

print(f"Instance name: {inst.name}")
print(f"Instance type property: {inst.type}")
print(f"Instance status: {inst.status}")

# Get raw API response
raw = inst.api.get().json()
print(f"\n=== Full API Response ===")
print(json.dumps(raw, indent=2))
