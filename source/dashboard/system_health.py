"""Read lightweight Pi health counters without contacting the radio."""
import math
import os
import shutil
from pathlib import Path


def host_health(disk_path, root=Path('/')):
    """Return OS metrics; unavailable counters are null, never invented zeros."""
    result = dict(uptime_seconds=None, cpu_temperature_c=None,
                  load_1m=None, cpu_cores=os.cpu_count(),
                  memory_total_bytes=None, memory_available_bytes=None,
                  disk_total_bytes=None, disk_free_bytes=None)
    try:
        value = float((root / 'proc/uptime').read_text().split()[0])
        if math.isfinite(value) and value >= 0:
            result['uptime_seconds'] = value
    except (OSError, ValueError, IndexError):
        pass
    try:
        value = float((root / 'sys/class/thermal/thermal_zone0/temp').read_text()) / 1000
        if math.isfinite(value) and -40 <= value <= 150:
            result['cpu_temperature_c'] = value
    except (OSError, ValueError):
        pass
    try:
        value = float((root / 'proc/loadavg').read_text().split()[0])
        if math.isfinite(value) and value >= 0:
            result['load_1m'] = value
    except (OSError, ValueError, IndexError):
        pass
    try:
        memory = {}
        for line in (root / 'proc/meminfo').read_text().splitlines():
            key, _, value = line.partition(':')
            if key in ('MemTotal', 'MemAvailable'):
                memory[key] = int(value.split()[0]) * 1024
        total, available = memory.get('MemTotal'), memory.get('MemAvailable')
        if total is not None and available is not None and total > 0 and 0 <= available <= total:
            result.update(memory_total_bytes=total, memory_available_bytes=available)
    except (OSError, ValueError, IndexError):
        pass
    try:
        disk = shutil.disk_usage(disk_path)
        result.update(disk_total_bytes=disk.total, disk_free_bytes=disk.free)
    except OSError:
        pass
    return result
