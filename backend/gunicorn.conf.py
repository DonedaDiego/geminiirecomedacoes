import os

bind = f"0.0.0.0:{os.environ.get('PORT', 10000)}"
workers = 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 120
keepalive = 2
graceful_timeout = 120

loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

preload_app = True
daemon = False
pidfile = None
user = None
group = None
tmp_upload_dir = None

if os.environ.get('FLASK_ENV') == 'development':
    reload = True
else:
    reload = False


def post_fork(server, worker):
    """Iniciar o Payment Scheduler dentro do worker (workers=1, sem duplicação).

    Threads não sobrevivem ao fork do gunicorn, por isso o scheduler
    precisa ser iniciado aqui e não no create_app().
    """
    try:
        from pag.payment_scheduler import start_payment_scheduler
        start_payment_scheduler()
        server.log.info("Payment Scheduler iniciado no worker %s", worker.pid)
    except Exception as e:
        server.log.error("Erro ao iniciar Payment Scheduler: %s", e)