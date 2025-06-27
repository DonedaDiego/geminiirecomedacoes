import os

# Configurações do servidor
bind = f"0.0.0.0:{os.environ.get('PORT', 10000)}"
workers = int(os.environ.get('WEB_CONCURRENCY', 2))
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 120
keepalive = 2

# Configurações de logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Configurações de processo
preload_app = True
daemon = False
pidfile = None
user = None
group = None
tmp_upload_dir = None

# Configurações de desenvolvimento vs produção
if os.environ.get('FLASK_ENV') == 'development':
    reload = True
    workers = 1
else:
    reload = False
    # Calcular workers baseado na CPU (2 * CPU cores + 1)
    try:
        import multiprocessing
        workers = min(multiprocessing.cpu_count() * 2 + 1, 4)  # Máximo 4 workers
    except:
        workers = 2

