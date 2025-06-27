# teste_ml.py
from swing_trade_ml_service import SwingTradeMachineLearningService

# Testar
service = SwingTradeMachineLearningService()
result = service.run_analysis('PETR4', 5)

if result['success']:
    print("✅ FUNCIONOU!")
    print(f"Preço atual: {result['analysis_data']['preco_atual']}")
    print(f"Direção: {result['analysis_data']['direcao']}")
else:
    print("❌ ERRO:", result['error'])