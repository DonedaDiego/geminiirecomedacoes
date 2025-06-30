#!/usr/bin/env python3
"""
Diagnóstico Rápido - Problema específico do Portfolio
Foca no problema: SQL executa mas frontend recebe erro de conexão
"""

import os
import psycopg2
import json

def quick_test():
    """Teste rápido para encontrar o problema"""
    
    print("🔥 DIAGNÓSTICO RÁPIDO - PORTFOLIO ASSETS")
    print("="*50)
    
    # 1. TESTE DE CONEXÃO
    print("1️⃣ Testando conexão...")
    try:
        database_url = os.environ.get("DATABASE_URL")
        
        if database_url:
            conn = psycopg2.connect(database_url, sslmode='require')
            print("✅ Conectado via DATABASE_URL")
        else:
            conn = psycopg2.connect(
                host=os.environ.get("DB_HOST", "localhost"),
                database=os.environ.get("DB_NAME", "postgres"), 
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD", "#geminii"),
                port=os.environ.get("DB_PORT", "5432")
            )
            print("✅ Conectado via variáveis locais")
            
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")
        return
    
    # 2. VERIFICAR TABELA
    print("\n2️⃣ Verificando tabela portfolio_assets...")
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM portfolio_assets")
        count = cursor.fetchone()[0]
        print(f"✅ Tabela existe com {count} registros")
    except Exception as e:
        print(f"❌ Tabela não existe: {e}")
        print("🔧 Criando tabela...")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_assets (
                id SERIAL PRIMARY KEY,
                portfolio_name VARCHAR(50) NOT NULL,
                ticker VARCHAR(10) NOT NULL,
                weight DECIMAL(5,2) DEFAULT 0,
                sector VARCHAR(100),
                entry_price DECIMAL(10,2),
                current_price DECIMAL(10,2),
                target_price DECIMAL(10,2),
                entry_date DATE,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(portfolio_name, ticker)
            );
        """)
        conn.commit()
        print("✅ Tabela criada!")
    
    # 3. TESTE DE INSERT EXATO
    print("\n3️⃣ Testando INSERT exato da API...")
    
    # Dados exatamente como vem do frontend
    test_data = {
        'portfolio': 'smart_bdr',
        'ticker': 'TEST4',
        'weight': 25.0,
        'sector': 'Teste', 
        'entry_price': 35.50,
        'current_price': 42.30,
        'target_price': 50.00,
        'entry_date': '2024-01-15'
    }
    
    try:
        # Verificar se já existe
        cursor.execute("""
            SELECT id FROM portfolio_assets 
            WHERE portfolio_name = %s AND ticker = %s
        """, (test_data['portfolio'], test_data['ticker']))
        
        existing = cursor.fetchone()
        if existing:
            cursor.execute("DELETE FROM portfolio_assets WHERE id = %s", (existing[0],))
            print(f"🗑️ Removido ativo existente (ID: {existing[0]})")
        
        # INSERT
        cursor.execute("""
            INSERT INTO portfolio_assets 
            (portfolio_name, ticker, weight, sector, entry_price, current_price, target_price, entry_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            test_data['portfolio'],
            test_data['ticker'], 
            float(test_data['weight']),
            test_data['sector'],
            float(test_data['entry_price']),
            float(test_data['current_price']) if test_data['current_price'] else None,
            float(test_data['target_price']),
            test_data['entry_date']
        ))
        
        asset_id = cursor.fetchone()[0]
        print(f"✅ INSERT executado - ID: {asset_id}")
        
        # COMMIT
        conn.commit()
        print("✅ COMMIT executado")
        
        # Verificar se salvou
        cursor.execute("SELECT ticker, weight FROM portfolio_assets WHERE id = %s", (asset_id,))
        saved = cursor.fetchone()
        if saved:
            print(f"✅ Ativo salvo: {saved[0]} - {saved[1]}%")
        else:
            print("❌ Ativo não foi salvo!")
        
        # Simular response da API
        response = {
            'success': True,
            'message': f'Ativo {test_data["ticker"]} adicionado à carteira {test_data["portfolio"]} com sucesso!'
        }
        print(f"📨 Response: {json.dumps(response)}")
        
        # Limpeza
        cursor.execute("DELETE FROM portfolio_assets WHERE id = %s", (asset_id,))
        conn.commit()
        print("🧹 Ativo de teste removido")
        
    except Exception as e:
        print(f"❌ ERRO no INSERT: {e}")
        print(f"Tipo: {type(e).__name__}")
        
        # Rollback se necessário
        try:
            conn.rollback()
        except:
            pass
    
    # 4. VERIFICAR OUTRAS TABELAS QUE PODEM CONFLITAR
    print("\n4️⃣ Verificando conflitos com outras tabelas...")
    
    conflicting_tables = [
        'recommendations_free',
        'portfolio_recommendations', 
        'recommendations'
    ]
    
    for table in conflicting_tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"📋 {table}: {count} registros")
        except:
            print(f"❌ {table}: Não existe")
    
    # 5. TESTE DE RESPONSE JSON
    print("\n5️⃣ Testando se JSON response está correto...")
    
    # Simular exatamente o que a API retorna
    test_responses = [
        {'success': True, 'message': 'Teste OK'},
        {'success': False, 'error': 'Teste Error'},
        {'success': True, 'message': 'Ativo TEST4 adicionado à carteira smart_bdr com sucesso!'}
    ]
    
    for resp in test_responses:
        try:
            json_str = json.dumps(resp)
            parsed = json.loads(json_str)
            print(f"✅ JSON válido: {json_str}")
        except Exception as e:
            print(f"❌ JSON inválido: {e}")
    
    cursor.close()
    conn.close()
    
    print(f"\n🎯 CONCLUSÃO:")
    print(f"- Se todos os testes acima passaram, o problema não é no banco")
    print(f"- O erro 'conexão' no frontend pode ser:")
    print(f"  1. Exceção não capturada APÓS o commit") 
    print(f"  2. Timeout na resposta HTTP")
    print(f"  3. Conflito de rota/blueprint")
    print(f"  4. Problema no JavaScript do frontend")
    print(f"\n💡 PRÓXIMO PASSO:")
    print(f"Verificar os logs do servidor durante a requisição")

def check_routes_conflict():
    """Verificar se há conflito entre rotas"""
    
    print("\n🛤️ VERIFICANDO CONFLITOS DE ROTAS...")
    print("="*40)
    
    # Verificar se existem múltiplos arquivos de routes
    route_files = [
        'recommendations_routes.py',
        'recommendations_routes_free.py', 
        'admin_routes.py'
    ]
    
    for file in route_files:
        if os.path.exists(file):
            print(f"✅ {file} existe")
            
            # Ler arquivo e procurar por rotas conflitantes
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Procurar por rotas de portfolio
                portfolio_routes = []
                lines = content.split('\n')
                
                for i, line in enumerate(lines):
                    if '@' in line and 'route(' in line and 'portfolio' in line.lower():
                        portfolio_routes.append(f"  Linha {i+1}: {line.strip()}")
                
                if portfolio_routes:
                    print(f"   📍 Rotas de portfolio encontradas:")
                    for route in portfolio_routes[:5]:  # Mostrar até 5
                        print(route)
                    if len(portfolio_routes) > 5:
                        print(f"   ... e mais {len(portfolio_routes) - 5} rotas")
                else:
                    print(f"   ➖ Nenhuma rota de portfolio encontrada")
                    
            except Exception as e:
                print(f"   ❌ Erro ao ler arquivo: {e}")
        else:
            print(f"❌ {file} não existe")

if __name__ == "__main__":
    print("🚀 DIAGNÓSTICO RÁPIDO")
    print("🎯 Foco: SQL executa mas frontend dá erro")
    print()
    
    choice = input("1. Teste rápido\n2. Verificar conflitos de rotas\n3. Ambos\n\nEscolha (1-3): ")
    
    if choice in ['1', '3']:
        quick_test()
    
    if choice in ['2', '3']:
        check_routes_conflict()
    
    print(f"\n🔍 INVESTIGAÇÃO ADICIONAL:")
    print(f"1. Verificar logs do servidor durante requisição")
    print(f"2. Testar rota direto no Postman/curl:")
    print(f"   POST /api/admin/portfolio/add-asset")
    print(f"   Headers: Authorization: Bearer TOKEN")
    print(f"   Body: JSON com dados do ativo")
    print(f"3. Verificar se há exceção não capturada após commit")
    print(f"4. Verificar se response está sendo retornado corretamente")