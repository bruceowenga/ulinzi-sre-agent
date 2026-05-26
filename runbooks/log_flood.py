import os
import subprocess


def rotate_logs(service_name: str) -> str:
    if os.getenv('DRY_RUN', 'false').lower() == 'true':
        return f'[DRY RUN] Would truncate logs for container: {service_name}'
    result = subprocess.run(
        ['docker', 'exec', service_name, 'sh', '-c', 'truncate -s 0 /proc/1/fd/1 /proc/1/fd/2'],
        capture_output=True,
        text=True,
    )
    return f'Rotated logs for {service_name}: {result.returncode}'