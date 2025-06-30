#!/usr/bin/env python3
"""
Teste Específico - Inserção de Ativos Portfolio
Replica exatamente o que a API /api/admin/portfolio/add-asset faz
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime

def test_exact_api_flow():
    """Testar exatamente o fluxo da API que está falhando"""
    
    print("🧪 TESTANDO FLUXO EXATO DA API add-asset")
    print("=" * 50)
    
    # Conectar exatamente como o database.py faz
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
        print(f"❌ ERRO DE CONEXÃO: {e}")
        return False
    
    cursor = conn.cursor()
    
    # Dados de teste exatamente como vem do frontend
    test_data = {
        'portfolio': 'smart_bdr',
        'ticker': 'WEGE3',
        'weight': 25.0,
        'sector': 'Industrial',
        'entry_price': 35.50,
        'current_price': 42.30,  # Pode ser None
        'target_price': 50.00,
        'entry_date': '2024-01-15'
    }
    
    print(f"📋 Dados de teste: {json.dumps(test_data, indent=2)}")
    
    try:
        # PASSO 1: Verificar se portfolio existe (como deveria ser)
        print("\n🔍 PASSO 1: Verificando portfolio...")
        cursor.execute("SELECT name, display_name FROM portfolios WHERE name = %s", (test_data['portfolio'],))
        portfolio = cursor.fetchone()
        
        if portfolio:
            print(f"✅ Portfolio encontrado: {portfolio[1]}")
        else:
            print(f"⚠️ Portfolio '{test_data['portfolio']}' não encontrado!")
            # Criar portfolio para teste
            cursor.execute("""
                INSERT INTO portfolios (name, display_name, description, is_active)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name) DO NOTHING
            """, (test_data['portfolio'], test_data['portfolio'].title(), 'Portfolio de teste', True))
            print("✅ Portfolio de teste criado")
        
        # PASSO 2: Verificar se ativo já existe
        print("\n🔍 PASSO 2: Verificando se ativo já existe...")
        cursor.execute("""
            SELECT id FROM portfolio_assets 
            WHERE portfolio_name = %s AND ticker = %s
        """, (test_data['portfolio'], test_data['ticker']))
        
        existing = cursor.fetchone()
        if existing:
            print(f"⚠️ Ativo {test_data['ticker']} já existe (ID: {existing[0]})")
            # Remover para o teste
            cursor.execute("DELETE FROM portfolio_assets WHERE id = %s", (existing[0],))
            print("🗑️ Ativo removido para o teste")
        else:
            print(f"✅ Ativo {test_data['ticker']} não existe - pode inserir")
        
        # PASSO 3: Inserção (exatamente como na API)
        print("\n💾 PASSO 3: Executando INSERT...")
        
        sql_query = """
            INSERT INTO portfolio_assets 
            (portfolio_name, ticker, weight, sector, entry_price, current_price, target_price, entry_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        values = (
            test_data['portfolio'],
            test_data['ticker'],
            float(test_data['weight']),
            test_data['sector'],
            float(test_data['entry_price']),
            float(test_data['current_price']) if test_data['current_price'] else None,
            float(test_data['target_price']),
            test_data['entry_date']
        )
        
        print(f"📝 SQL: {sql_query}")
        print(f"📊 Valores: {values}")
        
        cursor.execute(sql_query, values)
        asset_id = cursor.fetchone()[0]
        
        print(f"✅ INSERT executado! ID retornado: {asset_id}")
        
        # PASSO 4: Commit (crítico!)
        print("\n💾 PASSO 4: Executando COMMIT...")
        conn.commit()
        print("✅ COMMIT executado com sucesso!")
        
        # PASSO 5: Verificar se realmente foi salvo
        print("\n🔍 PASSO 5: Verificando se foi salvo...")
        cursor.execute("""
            SELECT id, ticker, weight, sector, entry_price, current_price, target_price, entry_date
            FROM portfolio_assets 
            WHERE id = %s
        """, (asset_id,))
        
        saved_asset = cursor.fetchone()
        if saved_asset:
            print("✅ Ativo encontrado no banco:")
            print(f"   ID: {saved_asset[0]}")
            print(f"   Ticker: {saved_asset[1]}")
            print(f"   Peso: {saved_asset[2]}%")
            print(f"   Setor: {saved_asset[3]}")
            print(f"   Preço Entrada: R$ {saved_asset[4]}")
            print(f"   Preço Atual: R$ {saved_asset[5] or 'N/A'}")
            print(f"   Preço Alvo: R$ {saved_asset[6]}")
            print(f"   Data: {saved_asset[7]}")
        else:
            print("❌ ERRO: Ativo não encontrado após commit!")
            return False
        
        # PASSO 6: Simular response da API
        print("\n📤 PASSO 6: Simulando response da API...")
        
        api_response = {
            'success': True,
            'message': f'Ativo {test_data["ticker"]} adicionado à carteira {test_data["portfolio"]} com sucesso!'
        }
        
        print(f"📨 Response: {json.dumps(api_response, indent=2)}")
        
        # LIMPEZA: Remover ativo de teste
        print("\n🧹 LIMPEZA: Removendo ativo de teste...")
        cursor.execute("DELETE FROM portfolio_assets WHERE id = %s", (asset_id,))
        conn.commit()
        print("✅ Ativo de teste removido")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO durante o teste: {e}")
        print(f"🔍 Tipo do erro: {type(e).__name__}")
        
        # Tentar rollback
        try:
            conn.rollback()
            print("🔄 Rollback executado")
        except:
            pass
            
        return False
        
    finally:
        cursor.close()
        conn.close()
        print("\n🔌 Conexão fechada")

def test_recommendations_table():
    """Testar se não há conflito com tabela de recomendações"""
    
    print("\n🔍 TESTANDO TABELA DE RECOMENDAÇÕES...")
    print("=" * 50)
    
    try:
        database_url = os.environ.get("DATABASE_URL")
        
        if database_url:
            conn = psycopg2.connect(database_url, sslmode='require')
        else:
            conn = psycopg2.connect(
                host=os.environ.get("DB_HOST", "localhost"),
                database=os.environ.get("DB_NAME", "postgres"),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD", "#geminii"),
                port=os.environ.get("DB_PORT", "5432")
            )
            
        cursor = conn.cursor()
        
        # Verificar tabelas de recomendações
        tables_to_check = [
            'portfolio_recommendations',
            'recommendations_free', 
            'recommendations'
        ]
        
        for table in tables_to_check:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"✅ {table}: {count} registros")
                
                # Ver estrutura
                cursor.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{table}'
                    ORDER BY ordinal_position
                """)
                columns = [row[0] for row in cursor.fetchall()]
                print(f"   Colunas: {', '.join(columns)}")
                
            except Exception as e:
                print(f"❌ {table}: Não existe ou erro - {e}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro ao testar recomendações: {e}")

def test_connection_persistence():
    """Testar se conexão persiste durante toda operação"""
    
    print("\n🔍 TESTANDO PERSISTÊNCIA DA CONEXÃO...")
    print("=" * 50)
    
    try:
        database_url = os.environ.get("DATABASE_URL")
        
        if database_url:
            conn = psycopg2.connect(database_url, sslmode='require')
        else:
            conn = psycopg2.connect(
                host=os.environ.get("DB_HOST", "localhost"),
                database=os.environ.get("DB_NAME", "postgres"),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD", "#geminii"),
                port=os.environ.get("DB_PORT", "5432")
            )
            
        print("✅ Conexão estabelecida")
        
        cursor = conn.cursor()
        
        # Teste 1: Query simples
        cursor.execute("SELECT 1")
        result = cursor.fetchone()[0]
        print(f"✅ Query básica: {result}")
        
        # Teste 2: Query com parâmetros
        cursor.execute("SELECT %s as test", ("test_param",))
        result = cursor.fetchone()[0]
        print(f"✅ Query com parâmetros: {result}")
        
        # Teste 3: BEGIN/COMMIT
        cursor.execute("BEGIN")
        print("✅ BEGIN executado")
        
        cursor.execute("SELECT 1")
        cursor.fetchone()
        print("✅ Query dentro da transação")
        
        cursor.execute("COMMIT")
        print("✅ COMMIT executado")
        
        # Teste 4: Verificar status da conexão
        print(f"📊 Status da conexão: {conn.status}")
        print(f"📊 Closed: {conn.closed}")
        print(f"📊 Encoding: {conn.encoding}")
        
        cursor.close()
        conn.close()
        
        print("✅ Todos os testes de conexão passaram!")
        return True
        
    except Exception as e:
        print(f"❌ Erro na persistência da conexão: {e}")
        return False

def check_api_error_patterns():
    """Verificar padrões comuns de erro na API"""
    
    print("\n🔍 VERIFICANDO PADRÕES DE ERRO NA API...")
    print("=" * 50)
    
    # Verificar problemas comuns
    issues = []
    
    # 1. Verificar se todas as variáveis de ambiente estão definidas
    env_vars = ['DATABASE_URL', 'DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_PORT']
    missing_vars = []
    
    for var in env_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if os.environ.get('DATABASE_URL'):
        print("✅ DATABASE_URL definida (Railway)")
    elif missing_vars:
        print(f"⚠️ Variáveis de ambiente faltando: {missing_vars}")
        issues.append("Variáveis de ambiente não configuradas")
    else:
        print("✅ Variáveis de ambiente locais definidas")
    
    # 2. Verificar se as tabelas realmente existem
    try:
        database_url = os.environ.get("DATABASE_URL")
        
        if database_url:
            conn = psycopg2.connect(database_url, sslmode='require')
        else:
            conn = psycopg2.connect(
                host=os.environ.get("DB_HOST", "localhost"),
                database=os.environ.get("DB_NAME", "postgres"),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD", "#geminii"),
                port=os.environ.get("DB_PORT", "5432")
            )
            
        cursor = conn.cursor()
        
        # Verificar tabela portfolio_assets
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = 'portfolio_assets'
        """)
        
        if cursor.fetchone():
            print("✅ Tabela portfolio_assets existe")
        else:
            print("❌ Tabela portfolio_assets NÃO existe!")
            issues.append("Tabela portfolio_assets não existe")
        
        # Verificar estrutura da tabela
        cursor.execute("""
            SELECT column_name, data_type, column_default, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'portfolio_assets'
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        if columns:
            print(f"📋 Estrutura da tabela portfolio_assets ({len(columns)} colunas):")
            for col in columns:
                nullable = "NULL" if col[3] == "YES" else "NOT NULL"
                default = f"DEFAULT {col[2]}" if col[2] else ""
                print(f"   - {col[0]} ({col[1]}) {nullable} {default}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro ao verificar tabelas: {e}")
        issues.append(f"Erro de conexão: {e}")
    
    # 3. Verificar se o problema é no response da API
    print("\n🔍 POSSÍVEIS CAUSAS DO ERRO 'Erro de conexão':")
    print("1. SQL executa mas conn.commit() falha")
    print("2. Resposta JSON malformada")
    print("3. Exceção não capturada após o SQL")
    print("4. Timeout na conexão")
    print("5. Conflito entre tabelas recommendations")
    
    if issues:
        print(f"\n❌ Problemas encontrados: {len(issues)}")
        for i, issue in enumerate(issues, 1):
            print(f"{i}. {issue}")
    else:
        print("\n✅ Nenhum problema óbvio encontrado")
    
    return len(issues) == 0

def simulate_exact_frontend_request():
    """Simular exatamente a requisição que vem do frontend"""
    
    print("\n🌐 SIMULANDO REQUISIÇÃO EXATA DO FRONTEND...")
    print("=" * 50)
    
    # Esta é a requisição que o JavaScript está fazendo
    request_data = {
        "portfolio": "smart_bdr",
        "ticker": "WEGE3",
        "weight": 25.0,
        "sector": "Industrial",
        "entry_price": 35.50,
        "current_price": 42.30,
        "target_price": 50.00,
        "entry_date": "2024-01-15"
    }
    
    print("📤 Dados da requisição:")
    print(json.dumps(request_data, indent=2))
    
    try:
        # Conectar como a API faz
        database_url = os.environ.get("DATABASE_URL")
        
        if database_url:
            conn = psycopg2.connect(database_url, sslmode='require')
        else:
            conn = psycopg2.connect(
                host=os.environ.get("DB_HOST", "localhost"),
                database=os.environ.get("DB_NAME", "postgres"),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD", "#geminii"),
                port=os.environ.get("DB_PORT", "5432")
            )
        
        cursor = conn.cursor()
        
        # Validações como na API
        portfolio = request_data.get('portfolio')
        ticker = request_data.get('ticker', '').upper()
        weight = request_data.get('weight')
        sector = request_data.get('sector', '').strip()
        entry_price = request_data.get('entry_price')
        current_price = request_data.get('current_price')
        target_price = request_data.get('target_price')
        entry_date = request_data.get('entry_date')
        
        print(f"\n🔍 Validações:")
        print(f"   Portfolio: {portfolio}")
        print(f"   Ticker: {ticker}")
        print(f"   Weight: {weight} ({type(weight)})")
        print(f"   Sector: {sector}")
        print(f"   Entry Price: {entry_price} ({type(entry_price)})")
        print(f"   Current Price: {current_price} ({type(current_price)})")
        print(f"   Target Price: {target_price} ({type(target_price)})")
        print(f"   Entry Date: {entry_date}")
        
        # Verificar se todos os campos obrigatórios estão presentes
        required = [portfolio, ticker, weight, sector, entry_price, target_price, entry_date]
        missing = []
        
        for i, field in enumerate(['portfolio', 'ticker', 'weight', 'sector', 'entry_price', 'target_price', 'entry_date']):
            if not required[i]:
                missing.append(field)
        
        if missing:
            print(f"❌ Campos obrigatórios faltando: {missing}")
            return False
        
        # Verificar peso
        if weight < 0 or weight > 100:
            print(f"❌ Peso inválido: {weight} (deve estar entre 0 e 100)")
            return False
        
        print("✅ Todas as validações passaram")
        
        # Verificar se ativo já existe
        cursor.execute("""
            SELECT id FROM portfolio_assets 
            WHERE portfolio_name = %s AND ticker = %s
        """, (portfolio, ticker))
        
        existing = cursor.fetchone()
        if existing:
            print(f"❌ Ativo {ticker} já existe na carteira {portfolio} (ID: {existing[0]})")
            return False
        
        print("✅ Ativo não existe - pode inserir")
        
        # Executar INSERT exatamente como na API
        print("\n💾 Executando INSERT...")
        
        cursor.execute("""
            INSERT INTO portfolio_assets 
            (portfolio_name, ticker, weight, sector, entry_price, current_price, target_price, entry_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            portfolio, 
            ticker, 
            float(weight), 
            sector, 
            float(entry_price) if entry_price else None,
            float(current_price) if current_price else None, 
            float(target_price) if target_price else None, 
            entry_date
        ))
        
        asset_id = cursor.fetchone()[0]
        print(f"✅ SQL executado! ID: {asset_id}")
        
        # COMMIT
        conn.commit()
        print("✅ COMMIT executado")
        
        # Simular response
        response = {
            'success': True,
            'message': f'Ativo {ticker} adicionado à carteira {portfolio} com sucesso!'
        }
        
        print(f"\n📨 Response simulado:")
        print(json.dumps(response, indent=2))
        
        # Limpeza
        cursor.execute("DELETE FROM portfolio_assets WHERE id = %s", (asset_id,))
        conn.commit()
        print("🧹 Ativo de teste removido")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 SIMULAÇÃO COMPLETA - TUDO FUNCIONOU!")
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO na simulação: {e}")
        print(f"🔍 Tipo: {type(e).__name__}")
        
        # Informações extras sobre o erro
        import traceback
        print(f"📋 Traceback completo:")
        traceback.print_exc()
        
        return False

if __name__ == "__main__":
    print("🚀 TESTE ESPECÍFICO - INSERÇÃO DE ATIVOS")
    print("🎯 Identifica exatamente onde está falhando")
    print()
    
    # Menu de testes
    tests = [
        ("1", "Testar fluxo completo da API", test_exact_api_flow),
        ("2", "Verificar tabela de recomendações", test_recommendations_table), 
        ("3", "Testar persistência da conexão", test_connection_persistence),
        ("4", "Verificar padrões de erro", check_api_error_patterns),
        ("5", "Simular requisição do frontend", simulate_exact_frontend_request),
        ("0", "Executar todos os testes", None)
    ]
    
    print("Escolha o teste:")
    for option, description, _ in tests:
        print(f"{option}. {description}")
    
    choice = input("\nDigite o número do teste: ").strip()
    
    if choice == "0":
        print("\n🔄 EXECUTANDO TODOS OS TESTES...\n")
        all_passed = True
        
        for _, description, test_func in tests[:-1]:  # Pular o "todos os testes"
            print(f"\n{'='*60}")
            print(f"🧪 {description.upper()}")
            print(f"{'='*60}")
            
            if test_func:
                try:
                    result = test_func()
                    if not result:
                        all_passed = False
                except Exception as e:
                    print(f"❌ Erro no teste: {e}")
                    all_passed = False
        
        print(f"\n{'='*60}")
        print(f"📊 RESULTADO FINAL: {'✅ TODOS OS TESTES PASSARAM' if all_passed else '❌ ALGUNS TESTES FALHARAM'}")
        print(f"{'='*60}")
        
    else:
        # Executar teste específico
        test_found = False
        for option, description, test_func in tests:
            if option == choice and test_func:
                print(f"\n🧪 Executando: {description}")
                print("="*50)
                try:
                    result = test_func()
                    print(f"\n🏁 Resultado: {'✅ SUCESSO' if result else '❌ FALHOU'}")
                except Exception as e:
                    print(f"\n❌ Erro durante o teste: {e}")
                    import traceback
                    traceback.print_exc()
                test_found = True
                break
        
        if not test_found:
            print("❌ Opção inválida!")
    
    print(f"\n💡 DICA: Se SQL executa mas frontend dá erro de conexão:")
    print("   1. Verificar se response JSON está correto")
    print("   2. Verificar se não há exceção após commit")
    print("   3. Verificar logs do servidor em tempo real")
    print("   4. Testar rota direto no Postman")
    print("\n🎯 Execute este script para identificar o problema exato!")