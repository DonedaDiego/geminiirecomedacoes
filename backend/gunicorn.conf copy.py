import os

# Configurações do servidor
bind = f"0.0.0.0:{os.environ.get('PORT', 10000)}"
workers = 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 120
keepalive = 2
graceful_timeout = 30  #  ADICIONAR ISSO

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
else:
    reload = False