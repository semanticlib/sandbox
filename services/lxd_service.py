"""LXD service for instance management"""
import time
from typing import Optional, Dict, Any, List


class LXDService:
    """Service for LXD operations"""

    def __init__(self, db_session):
        self.db = db_session
        self.client = None

    def get_client(self):
        """Get LXD client based on settings"""
        from services.lxd_client import get_lxd_client
        from core.models import LXDSettings

        settings = self.db.query(LXDSettings).first()
        if not settings:
            return None

        if settings.use_socket:
            self.client = get_lxd_client(
                use_socket=True,
                verify_ssl=settings.verify_ssl,
                cert=settings.client_cert,
                key=settings.client_key
            )
        elif settings.server_url:
            self.client = get_lxd_client(
                settings.server_url,
                verify_ssl=settings.verify_ssl,
                cert=settings.client_cert,
                key=settings.client_key
            )
        return self.client

    def is_connected(self) -> bool:
        """Check if connected to LXD"""
        return self.client is not None

    def get_all_instances(self) -> List[Dict[str, Any]]:
        """Get all instances with their details"""
        if not self.client:
            return []

        instances = []
        all_instances = self.client.instances.all()

        for inst in all_instances:
            try:
                cpu = 'N/A'
                memory_usage = 'N/A'
                memory_allocated = 'N/A'

                # Get allocated resources from instance config
                allocated_cpu = inst.config.get('limits.cpu')
                if allocated_cpu:
                    cpu = allocated_cpu

                allocated_memory = inst.config.get('limits.memory') or inst.config.get('boot.memory')
                if allocated_memory:
                    memory_allocated = allocated_memory

                # For running instances: get actual usage from state
                if inst.status == 'Running':
                    try:
                        state = inst.state
                        memory_state = getattr(state, 'memory', None)
                        if memory_state and hasattr(memory_state, 'usage'):
                            memory_usage = memory_state.usage  # in bytes
                    except Exception:
                        pass

                # Format memory as usage/allocated if both available
                if memory_usage != 'N/A' and memory_allocated != 'N/A':
                    memory = f"{memory_usage}/{memory_allocated}"
                elif memory_allocated != 'N/A':
                    memory = memory_allocated
                elif memory_usage != 'N/A':
                    memory = memory_usage
                else:
                    memory = 'N/A'

                # If CPU is still N/A, check if it's a VM without limits
                if cpu == 'N/A' and inst.type == 'virtual-machine':
                    cpu = 'default'

                # Get disk size from instance devices
                disk = 'N/A'
                root_device = inst.devices.get('root', {})
                if root_device and 'size' in root_device:
                    disk = root_device['size']

                # Get IP address from instance state (for running instances)
                ip_address = 'N/A'
                if inst.status == 'Running':
                    try:
                        # Call state() as a method - returns InstanceState object
                        state = inst.state()
                        # Access network as an attribute (not dict key)
                        network = state.network
                        if network:
                            # Look for any interface with IPv4 address
                            for iface_name, iface_data in network.items():
                                # Get addresses for this interface
                                addresses = iface_data.get('addresses', [])
                                for addr in addresses:
                                    if addr.get('family') == 'inet':
                                        ip_address = addr.get('address', 'N/A')
                                        break
                                if ip_address != 'N/A':
                                    break
                    except Exception:
                        pass

                instances.append({
                    'name': inst.name,
                    'status': inst.status,
                    'type': inst.type,
                    'cpu': cpu,
                    'memory': memory,
                    'disk': disk,
                    'ip': ip_address,
                })
            except Exception:
                instances.append({
                    'name': inst.name,
                    'status': inst.status,
                    'type': inst.type,
                    'cpu': 'N/A',
                    'memory': 'N/A',
                    'disk': 'N/A',
                    'ip': 'N/A',
                })

        return instances

    def get_instance_stats(self) -> Dict[str, Any]:
        """Get instance statistics"""
        if not self.client:
            return {"total": 0, "running": 0, "connected": False}

        try:
            all_instances = self.client.instances.all()
            return {
                "total": len(all_instances),
                "running": sum(1 for i in all_instances if i.status == "Running"),
                "connected": True
            }
        except Exception:
            return {"total": 0, "running": 0, "connected": False}

    def start_instance(self, name: str) -> Dict[str, Any]:
        """Start an instance"""
        try:
            instance = self.client.instances.get(name)
            instance.start()
            return {"success": True, "message": f"Instance {name} started"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def stop_instance(self, name: str) -> Dict[str, Any]:
        """Stop an instance"""
        try:
            instance = self.client.instances.get(name)
            instance.stop()
            return {"success": True, "message": f"Instance {name} stopped"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def delete_instance(self, name: str, force: bool = False) -> Dict[str, Any]:
        """Delete an instance"""
        try:
            instance = self.client.instances.get(name)

            # Stop instance first if running and not force delete
            if instance.status == "Running" and not force:
                return {
                    "success": False,
                    "message": f"Instance '{name}' is running. Stop it first or check 'Force delete'."
                }

            # Delete the instance
            instance.delete(wait=True)
            return {"success": True, "message": f"Instance '{name}' deleted successfully"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def instance_exists(self, name: str) -> bool:
        """Check if an instance exists"""
        try:
            existing = self.client.instances.get(name)
            return existing is not None
        except Exception:
            return False

    def test_connection(self) -> Dict[str, Any]:
        """Test LXD connection"""
        from core.models import LXDSettings

        settings = self.db.query(LXDSettings).first()
        if not settings:
            return {"success": False, "message": "No LXD settings configured"}

        # Socket connection doesn't require certificate
        if not settings.use_socket and (not settings.client_cert or not settings.client_key):
            return {"success": False, "message": "Certificate and Key are required for HTTPS connection. Please paste them in the settings form."}

        try:
            if not self.client:
                self.get_client()

            server = self.client.api.get().json()
            connection_type = "Unix socket" if settings.use_socket else "HTTPS"
            return {
                "success": True,
                "message": f"Connected to LXD server via {connection_type}: {server.get('environment', {}).get('server_name', 'unknown')}"
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
