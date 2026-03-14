#!/usr/bin/env python3
"""Debug script to check state() return type"""
import sys
sys.path.insert(0, '.')

from services.lxd_client import get_lxd_client

client = get_lxd_client(use_socket=True)
inst = client.instances.get('dspace2')

print(f"Instance: {inst.name}")
print(f"Status: {inst.status}")

# Call state as method
state = inst.state()
print(f"\nstate() type: {type(state)}")
print(f"state() dir: {[x for x in dir(state) if not x.startswith('_')][:15]}")

# Check if it's an object or dict
if hasattr(state, 'network'):
    print(f"\nHas 'network' attribute")
    network = state.network
    print(f"network type: {type(network)}")
    print(f"network: {network}")
elif isinstance(state, dict):
    print(f"\nIs a dict")
    network = state.get('network', {})
    print(f"network: {network}")
else:
    print(f"\nUnknown type")
    print(f"state: {state}")
