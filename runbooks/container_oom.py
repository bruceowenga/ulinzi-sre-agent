import os
import docker

def restart_container(service_name: str) -> str:
    if os.getenv('DRY_RUN', 'false').lower() == 'true':
        return f'[DRY RUN] Would restart container: {service_name}'
    client = docker.from_env()
    client.containers.get(service_name).restart()
    return f'Restarted container: {service_name}'