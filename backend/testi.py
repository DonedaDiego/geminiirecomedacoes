#!/usr/bin/env python3
# setup_recommendations.py - SCRIPT PARA CONFIGURAR RECOMENDAÇÕES FREE
# ===================================================================

import sys
import os

def main():
    """Script principal para configurar sistema de recomendações"""
    
    print("🔥 === SETUP RECOMENDAÇÕES FREE GEMINII ===")
    print("=" * 50)
    
    try:
        # 1. Verificar dependências
        print("\n1️⃣ VERIFICANDO DEPENDÊNCIAS...")
        
        required_modules = ['psycopg2', 'flask', 'yfinance', 'pandas', 'numpy']
        missing_modules = []
        
        for module in required_modules:
            try:
                __import__(module)
                print(f"   ✅ {module}")
            except ImportError:
                print(f"   ❌ {module} - AUSENTE")
                missing_modules.append(module)
        
        if missing_modules:
            print(f"\n❌ Instale os módulos ausentes:")
            print(f"pip install {' '.join(missing_modules)}")
            return False
        
        # 2. Configurar banco de dados
        print("\n2️⃣ CONFIGURANDO BANCO DE DADOS...")
        
        from database import setup_enhanced_database, verify_service_compatibility
        
        if setup_enhanced_database():
            print("   ✅ Banco configurado com sucesso")
            
            if verify_service_compatibility():
                print("   ✅ Compatibilidade verificada")
            else:
                print("   ⚠️ Alguns problemas de compatibilidade detectados")
        else:
            print("   ❌ Falha na configuração do banco")
            return False
        
        # 3. Testar serviço de recomendações
        print("\n3️⃣ TESTANDO SERVIÇO DE RECOMENDAÇÕES...")
        
        from recommendations_service_free import RecommendationsServiceFree, create_recommendations_table
        
        # Criar tabela se não existir
        if create_recommendations_table():
            print("   ✅ Tabela recommendations_free verificada")
        else:
            print("   ❌ Problemas na tabela recommendations_free")
            return False
        
        # Testar conexão com yfinance
        print("   🔍 Testando integração yfinance...")
        test_data = RecommendationsServiceFree.get_stock_data('PETR4')
        if test_data:
            print(f"   ✅ yfinance funcionando - PETR4: R$ {test_data['current_price']:.2f}")
        else:
            print("   ⚠️ yfinance com problemas, mas sistema pode funcionar")
        
        # 4. Verificar rotas
        print("\n4️⃣ VERIFICANDO ROTAS...")
        
        from recommendations_routes_free import get_recommendations_free_blueprint
        
        try:
            blueprint = get_recommendations_free_blueprint()
            print(f"   ✅ Blueprint criado: {blueprint.name}")
            print(f"   ✅ URL prefix: {blueprint.url_prefix}")
        except Exception as e:
            print(f"   ❌ Erro no blueprint: {e}")
            return False
        
        # 5. Teste completo de integração
        print("\n5️⃣ TESTE DE INTEGRAÇÃO...")
        
        # Tentar carregar recomendações existentes
        recommendations = RecommendationsServiceFree.get_active_recommendations()
        print(f"   📊 Recomendações ativas encontradas: {len(recommendations)}")
        
        # Tentar calcular estatísticas
        stats = RecommendationsServiceFree.get_statistics()
        if stats:
            print(f"   📈 Estatísticas calculadas - Taxa de sucesso: {stats['success_rate']:.1f}%")
        else:
            print("   📈 Nenhuma estatística disponível (normal para sistema novo)")
        
        # 6. Resultado final
        print("\n" + "=" * 50)
        print("✅ SETUP CONCLUÍDO COM SUCESSO!")
        print("\n📋 PRÓXIMOS PASSOS:")
        print("1. Execute seu app Flask principal")
        print("2. Acesse o admin dashboard")
        print("3. Navegue para 'Recomendações Free'")
        print("4. Teste criação de recomendações")
        print("\n🌐 ENDPOINTS DISPONÍVEIS:")
        print("   GET  /api/recommendations/free/active")
        print("   GET  /api/recommendations/free/statistics")
        print("   POST /api/recommendations/admin/create-single")
        print("   POST /api/recommendations/admin/generate")
        print("   POST /api/recommendations/admin/update-prices")
        print("\n🔑 AUTENTICAÇÃO:")
        print("   Todas as rotas admin requerem token Bearer")
        print("   Usuário deve ter user_type='admin' ou 'master'")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO DURANTE SETUP: {e}")
        import traceback
        traceback.print_exc()
        return False

def quick_test():
    """Teste rápido das funcionalidades principais"""
    
    print("\n🧪 === TESTE RÁPIDO ===")
    
    try:
        # Teste 1: Conexão com banco
        from database import test_connection
        if test_connection():
            print("✅ Conexão com banco OK")
        else:
            print("❌ Falha na conexão com banco")
            return False
        
        # Teste 2: yfinance
        from recommendations_service_free import RecommendationsServiceFree
        stock_data = RecommendationsServiceFree.get_stock_data('VALE3')
        if stock_data:
            print(f"✅ yfinance OK - VALE3: R$ {stock_data['current_price']:.2f}")
        else:
            print("⚠️ yfinance com problemas")
        
        # Teste 3: Tabela de recomendações
        recommendations = RecommendationsServiceFree.get_active_recommendations()
        print(f"✅ Tabela OK - {len(recommendations)} recomendações encontradas")
        
        print("✅ Todos os testes passaram!")
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        return False

if __name__ == "__main__":
    print("Geminii - Setup de Recomendações Free")
    print("Escolha uma opção:")
    print("1. Setup completo")
    print("2. Teste rápido")
    print("3. Sair")
    
    choice = input("\nDigite sua escolha (1-3): ").strip()
    
    if choice == "1":
        success = main()
        sys.exit(0 if success else 1)
    elif choice == "2":
        success = quick_test()
        sys.exit(0 if success else 1)
    elif choice == "3":
        print("👋 Saindo...")
        sys.exit(0)
    else:
        print("❌ Opção inválida")
        sys.exit(1)