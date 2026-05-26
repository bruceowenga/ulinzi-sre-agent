from runbooks.container_oom import restart_container
from runbooks.disk_pressure import prune_docker
from runbooks.log_flood import rotate_logs

REGISTRY: dict[str, callable] = {
    'ContainerOOM':         restart_container,
    'ContainerRestartLoop': restart_container,
    'HighDisk':             prune_docker,
    'LokiIngestionStopped': rotate_logs,
}

def get_runbook(alert_name: str):
    return REGISTRY.get(alert_name)