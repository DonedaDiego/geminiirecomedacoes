import os
from dotenv import load_dotenv

# Carregar .env
load_dotenv()

# Tentar diferentes chaves possíveis
possible_keys = [
    os.getenv('JWT_SECRET'),
    os.getenv('SECRET_KEY'), 
    'geminii-jwt-secret-key-2024',
    'geminii-local-dev',
    'fallback-secret'
]

# Filtrar apenas as que existem
JWT_KEYS_TO_TRY = [key for key in possible_keys if key]

# Usar a primeira disponível como padrão
JWT_SECRET = JWT_KEYS_TO_TRY[0] if JWT_KEYS_TO_TRY else 'geminii-jwt-secret-key-2024'
OPLAB_TOKEN = os.getenv('OPLAB_TOKEN', '')

