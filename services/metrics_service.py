"""System metrics service using psutil"""
import psutil


def get_system_metrics():
    """Get current system metrics (CPU, memory, disk)"""
    try:
        # CPU usage percentage
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Memory usage
        memory = psutil.virtual_memory()
        memory_used = memory.used
        memory_total = memory.total
        memory_percent = memory.percent

        # Disk usage (root partition)
        disk = psutil.disk_usage('/')
        disk_used = disk.used
        disk_total = disk.total
        disk_percent = disk.percent

        return {
            "cpu_percent": cpu_percent,
            "memory_used": memory_used,
            "memory_total": memory_total,
            "memory_percent": memory_percent,
            "disk_used": disk_used,
            "disk_total": disk_total,
            "disk_percent": disk_percent
        }
    except Exception:
        return {
            "cpu_percent": 0,
            "memory_used": 0,
            "memory_total": 0,
            "memory_percent": 0,
            "disk_used": 0,
            "disk_total": 0,
            "disk_percent": 0
        }
