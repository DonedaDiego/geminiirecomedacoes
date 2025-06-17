#!/usr/bin/env python3
"""
WSGI config para Geminii Tech
Para uso com Gunicorn em produção
"""

import os
import sys

# Adicionar diretório backend ao Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

# Importar aplicação Flask
from main import app

# Alias para WSGI
application = app

if __name__ == "__main__":
    application.run()