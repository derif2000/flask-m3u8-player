# gunicorn_config.py
import multiprocessing

# Configuración básica
bind = "0.0.0.0:5000"
workers = multiprocessing.cpu_count() * 2 + 1
threads = 4

# Ajustes de timeout para Selenium
timeout = 300  # 5 minutos
graceful_timeout = 300
keepalive = 75

# Configuración de logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Manejo de workers
max_requests = 1000
max_requests_jitter = 50
worker_class = "gthread"  # Usar threads para mejor manejo de I/O