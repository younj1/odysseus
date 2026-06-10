from aria.homelab import full_dashboard, system_health, check_services, docker_status

def print_dashboard():
    full_dashboard()

def serve_dashboard():
    import subprocess
    from aria.homelab import full_dashboard
    full_dashboard()
