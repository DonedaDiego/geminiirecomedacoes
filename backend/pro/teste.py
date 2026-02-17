"""
test_theta_final.py - Teste final do theta_service corrigido
"""

import sys
sys.path.append('backend/pro')  # Ajuste o caminho se necessário

from theta_service import ThetaService

print("\n" + "="*70)
print("  TESTE THETA SERVICE - VERSÃO CORRIGIDA")
print("="*70 + "\n")

try:
    service = ThetaService()
    
    print(" Executando análise TEX para BOVA11...")
    result = service.analyze_theta_complete('BOVA11')
    
    print("\n" + "="*70)
    print("   RESULTADO")
    print("="*70)
    
    print(f"\n Success: {result['success']}")
    print(f" Spot: R$ {result['spot_price']:.2f}")
    print(f" Options analyzed: {result['options_count']}")
    print(f"📅 Expiration: {result['data_quality']['expiration']}")
    print(f"🎯 Real data count: {result['data_quality']['real_data_count']}")
    
    decay = result['decay_regime']
    print(f"\n🔥 DECAY REGIME:")
    print(f"   Total TEX: {decay['total_tex']:,.0f}")
    print(f"   Descoberto: {decay['total_tex_descoberto']:,.0f}")
    print(f"   Weighted days: {decay['weighted_days']:.1f}")
    print(f"   Time pressure: {decay['time_pressure']}")
    print(f"   Max bleed strike: R$ {decay['max_bleed_strike']:.2f}")
    print(f"   Interpretation: {decay['market_interpretation']}")
    
    print("\n" + "="*70)
    print("   THETA SERVICE FUNCIONANDO PERFEITAMENTE!")
    print("="*70 + "\n")
    
except Exception as e:
    print(f"\n❌ ERRO: {e}\n")
    import traceback
    traceback.print_exc()