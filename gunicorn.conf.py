import os

bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"
workers = 1
worker_class = "sync"
accesslog = "-"
errorlog = "-"
loglevel = "info"
timeout = 120
