

import os
import sys

# Configurar path corretamente
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)

# Configurar ambiente para Railway
os.environ.setdefault('FLASK_ENV', 'production')

# Importar app
from main import create_app

# Criar aplicação
application = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    application.run(host="0.0.0.0", port=port)