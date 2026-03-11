#!/usr/bin/env python3
"""Test actual VM creation with pylxd"""

from pylxd import Client

client = Client()

# Get the VM image
vm_image = None
for img in client.images.all():
    desc = img.properties.get('description', '').lower()
    img_type = img.properties.get('type', '')
    if "ubuntu" in desc and "24.04" in desc and img_type in ["disk1.img", "virtual-machine"]:
        vm_image = img
        break

if not vm_image:
    print("No VM image found!")
    exit(1)

print(f"Using image: {vm_image.fingerprint[:12]}")

# Test 1: Create using virtual_machines.create()
print("\n=== Test 1: virtual_machines.create() ===")
try:
    config_data = {
        "name": "test-vm-pylxd",
        "source": {
            "type": "image",
            "fingerprint": vm_image.fingerprint
        },
        "config": {
            "limits.cpu": "2",
            "limits.memory": "4GiB",
        },
        "devices": {
            "root": {
                "type": "disk",
                "path": "/",
                "pool": "default",
                "size": "20GiB"
            }
        }
    }
    
    print("Creating VM...")
    vm = client.virtual_machines.create(config_data, wait=True)
    print(f"Success! VM created: {vm.name}, status: {vm.status}")
    
    # Clean up
    print("Deleting test VM...")
    vm.delete(wait=True)
    print("Test VM deleted")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Create using API directly
print("\n=== Test 2: API direct call ===")
try:
    config_data = {
        "name": "test-vm-api",
        "source": {
            "type": "image",
            "fingerprint": vm_image.fingerprint
        },
        "config": {
            "limits.cpu": "2",
            "limits.memory": "4GiB",
        },
        "devices": {
            "root": {
                "type": "disk",
                "path": "/",
                "pool": "default",
                "size": "20GiB"
            }
        },
        "type": "virtual-machine"
    }
    
    print("Creating VM via API...")
    response = client.api.instances.post(json=config_data)
    print(f"Response: {response.status_code}")
    
    # Wait for operation
    operation = response.json()["operation"]
    op_id = operation.split("/")[-1]
    print(f"Operation ID: {op_id}")
    
    # Wait for completion
    while True:
        op = client.operations.get(op_id)
        if op.status_code == 200:
            break
        import time
        time.sleep(1)
        print(f"Progress: {op.metadata.get('progress', 'N/A')}")
    
    print("VM created successfully!")
    
    # Clean up
    vm = client.virtual_machines.get("test-vm-api")
    print("Deleting test VM...")
    vm.delete(wait=True)
    print("Test VM deleted")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
