#!/usr/bin/env python3
"""
CLI script to check CPU and Memory allocation for all LXD instances.
Helps debug what values are available from pylxd.
"""

import sys
import json
from pylxd import Client


def main():
    try:
        client = Client()
        server_info = client.api.get().json()
        server_name = server_info.get('environment', {}).get('server_name', 'unknown')
        print(f"Connected to LXD server: {server_name}")
        print()
    except Exception as e:
        print(f"Failed to connect to LXD: {e}")
        print("\nMake sure:")
        print("  1. LXD is installed and running")
        print("  2. Your user is in the 'lxd' group (run: sudo usermod -aG lxd $USER)")
        print("  3. You have logged out and back in for group changes to take effect")
        sys.exit(1)

    instances = client.instances.all()
    
    if not instances:
        print("No instances found.")
        return

    print(f"{'Name':<20} {'Type':<10} {'Status':<12} {'CPU':<15} {'Memory':<15} {'Boot.Mem':<15} {'CPU (state)':<15} {'Memory (state)':<15}")
    print("-" * 130)

    for inst in instances:
        # Config values (always available)
        # For containers: limits.cpu, limits.memory
        # For VMs: boot.host_shutdown_timeout, limits.cpu (optional), but CPU/Mem are in inst.config with different keys
        
        # Container-style limits
        cpu_limits = inst.config.get('limits.cpu', 'N/A')
        memory_limits = inst.config.get('limits.memory', 'N/A')
        
        # VM-style boot config
        boot_memory = inst.config.get('boot.memory', 'N/A')
        boot_cpu = inst.config.get('boot.cpu', 'N/A')  # May not exist
        
        # Check for any cpu/memory related config
        all_cpu_keys = {k: v for k, v in inst.config.items() if 'cpu' in k.lower()}
        all_mem_keys = {k: v for k, v in inst.config.items() if 'memory' in k.lower() or 'mem' in k.lower()}
        
        # State values (only for running instances with guest agent for VMs)
        cpu_state = 'N/A'
        memory_state = 'N/A'
        
        if inst.status == 'Running':
            try:
                state = inst.state
                if state.cpu and hasattr(state.cpu, 'usage'):
                    cpu_state = f"{state.cpu.usage} ns"
                if state.memory and hasattr(state.memory, 'usage'):
                    memory_state = f"{state.memory.usage} bytes"
            except Exception as e:
                cpu_state = f"Error: {e}"
                memory_state = f"Error: {e}"

        # Determine display values
        cpu_display = cpu_limits if cpu_limits != 'N/A' else boot_cpu
        memory_display = memory_limits if memory_limits != 'N/A' else boot_memory
        
        print(f"{inst.name:<20} {inst.type:<10} {inst.status:<12} {cpu_display:<15} {memory_display:<15} {boot_memory:<15} {cpu_state:<15} {memory_state:<15}")
        
        # Print relevant config for debugging
        print(f"  CPU-related config: {all_cpu_keys if all_cpu_keys else 'None'}")
        print(f"  Memory-related config: {all_mem_keys if all_mem_keys else 'None'}")
        if inst.type == 'virtual-machine':
            print(f"  [VM] Check 'lxc config get {inst.name}' for hardware config - may use defaults")
            
            # Get raw instance data from API
            try:
                raw = inst.api.get().json()
                print(f"  [Raw API] Instance type: {raw.get('type', 'N/A')}")
                print(f"  [Raw API] Config keys: {list(raw.get('config', {}).keys())}")
                
                # Check devices for VM hardware config
                devices = raw.get('devices', {})
                print(f"  [Devices] Keys: {list(devices.keys())}")
                for dev_name, dev_config in devices.items():
                    print(f"    {dev_name}: {dev_config}")
                
                # For VMs, check expanded config
                if raw.get('type') == 'virtual-machine':
                    print(f"  [VM Hardware] Checking expanded config...")
                    # Try to get instance state which may have hardware info
                    try:
                        state_raw = inst.state
                        print(f"    State type: {type(state_raw)}")
                        print(f"    State dirs: {[d for d in dir(state_raw) if not d.startswith('_')]}")
                    except Exception as se:
                        print(f"    State error: {se}")
            except Exception as e:
                print(f"  [Error fetching raw data: {e}]")

    print()
    print("Note:")
    print("  - Config values come from instance configuration (always available)")
    print("  - State values come from runtime metrics (requires running + guest agent for VMs)")
    print()
    print("For VMs without explicit limits:")
    print("  - Run 'lxc config get <vm-name>' to see hardware allocation")
    print("  - VMs use defaults if not explicitly configured")


if __name__ == "__main__":
    main()
