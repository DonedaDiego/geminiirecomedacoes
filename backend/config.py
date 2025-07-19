import os
from datetime import timedelta

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


class Config:
    """Configurações base"""
    
    # API OpLab
    OPLAB_API_TOKEN = os.getenv('OPLAB_API_TOKEN', 
        "beczK/4WCP1n9eOkIqVi4cR+qIlvNST0mq7DfBvKzU1kBRF0rakIb/wnspMQ9qSx--FiV9LR+39n8REDQPYVGc6A==--N2E2OGM3M2YzYmQwMzM0MzE0MWRjNzU4ZThhMDJkMGE=")
    OPLAB_BASE_URL = "https://api.oplab.com.br/v3"
    
    # Configurações de Trading
    DEFAULT_START_DATE = "2020-01-01"
    DEFAULT_END_DATE = "2026-01-01"
    DEFAULT_FLOW_DAYS = 30
    MIN_FLOW_DAYS = 7
    MAX_FLOW_DAYS = 90
    
    # Configurações de ML
    GARCH_CONFIG = {
        'vol': 'Garch',
        'p': 1,
        'q': 1,
        'dist': 'Normal'
    }
    
    XGBOOST_CONFIG = {
        'n_estimators': 200,
        'max_depth': 8,
        'learning_rate': 0.05,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'reg_alpha': 0.1,
        'reg_lambda': 0.1,
        'random_state': 42,
        'verbosity': 0
    }
    
    # Configurações de Bandas
    BAND_SIGMAS = [2, 4]
    VOLATILITY_WINDOWS = [3, 5, 10, 20]
    FEATURE_WINDOWS = [5, 10, 20, 60]
    FEATURE_LAGS = [1, 2, 5]
    
    # Configurações de Charts
    DEFAULT_CHART_DAYS = 180
    MIN_DATA_POINTS = 100
    
    # Configurações de Flow
    MONEYNESS_THRESHOLDS = {
        'OTM_THRESHOLD': 0.95,
        'ITM_THRESHOLD': 1.05
    }
    
    # Configurações de IV Score
    IV_SCORE_THRESHOLDS = {
        'HIGH_CONFIDENCE': 70,
        'MEDIUM_CONFIDENCE': 40,
        'LOW_CONFIDENCE': 0
    }
    
    # Timeouts
    REQUEST_TIMEOUT = 30
    IV_REQUEST_TIMEOUT = 10
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

class DevelopmentConfig(Config):
    """Configurações de desenvolvimento"""
    DEBUG = True
    TESTING = False
    
class ProductionConfig(Config):
    """Configurações de produção"""
    DEBUG = False
    TESTING = False
    
    # Configurações mais conservadoras para produção
    REQUEST_TIMEOUT = 15
    IV_REQUEST_TIMEOUT = 5

class TestingConfig(Config):
    """Configurações de teste"""
    DEBUG = True
    TESTING = True
    
    # Usar dados mock em testes
    USE_MOCK_DATA = True

# Mapeamento de ambientes
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(env=None):
    """Retorna configuração baseada no ambiente"""
    env = env or os.getenv('FLASK_ENV', 'default')
    return config_map.get(env, DevelopmentConfig)