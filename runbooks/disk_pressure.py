import os
import subprocess


def prune_docker(service_name: str = '') -> str:
    if os.getenv('DRY_RUN', 'false').lower() == 'true':
        return '[DRY RUN] Would run: docker system prune -f'
    result = subprocess.run(
        ['docker', 'system', 'prune', '-f'],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or result.stderr.strip()
