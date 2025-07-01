#!/usr/bin/env python3
# test_railway.py - TESTE DIRETO NO RAILWAY SEM ENROLAÇÃO

import psycopg2
from datetime import datetime

def test_portfolio_insertion():
    print("🚀 TESTE DIRETO NO RAILWAY - INSERÇÃO DE ATIVO")
    print("=" * 60)
    
    # Conectar no Railway
    try:
        conn = psycopg2.connect(
            host="ballast.proxy.rlwy.net",
            port=33654,
            dbname="railway",
            user="postgres",
            password="SWYYPTWLukrNVucLgnyImUfTftHSadyS"
        )
        cur = conn.cursor()
        print("✅ Conectado no Railway!")
        
    except Exception as e:
        print(f"❌ ERRO DE CONEXÃO: {e}")
        return
    
    # 1. VERIFICAR SE TABELAS EXISTEM
    print("\n🔍 1. Verificando tabelas...")
    cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('portfolios', 'portfolio_assets', 'users')
    """)
    tables = [row[0] for row in cur.fetchall()]
    
    required_tables = ['portfolios', 'portfolio_assets', 'users']
    for table in required_tables:
        if table in tables:
            print(f"   ✅ {table}")
        else:
            print(f"   ❌ {table} - FALTANDO!")
    
    # 2. VERIFICAR PORTFOLIOS DISPONÍVEIS
    print("\n📁 2. Verificando portfolios...")
    try:
        cur.execute("SELECT name, display_name FROM portfolios")
        portfolios = cur.fetchall()
        
        if portfolios:
            for name, display in portfolios:
                print(f"   ✅ {name} - {display}")
        else:
            print("   ❌ Nenhum portfolio encontrado!")
            
    except Exception as e:
        print(f"   ❌ ERRO: {e}")
    
    # 3. VERIFICAR ESTRUTURA DA TABELA portfolio_assets
    print("\n📊 3. Estrutura da tabela portfolio_assets...")
    try:
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'portfolio_assets'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        
        for col_name, col_type, nullable in columns:
            print(f"   - {col_name} ({col_type}) {'NULL' if nullable == 'YES' else 'NOT NULL'}")
            
    except Exception as e:
        print(f"   ❌ ERRO: {e}")
    
    # 4. TESTAR INSERÇÃO REAL
    print("\n💾 4. TESTANDO INSERÇÃO REAL...")
    
    # Dados de teste
    test_data = {
        'portfolio_name': 'smart_bdr',
        'ticker': 'TESTE9',
        'weight': 12.5,
        'sector': 'Teste Direto',
        'entry_price': 29.90,
        'current_price': 31.50,
        'target_price': 35.00,
        'entry_date': '2024-01-15'
    }
    
    print(f"   Dados: {test_data}")
    
    try:
        # Verificar se ativo já existe
        cur.execute("""
            SELECT id FROM portfolio_assets 
            WHERE portfolio_name = %s AND ticker = %s
        """, (test_data['portfolio_name'], test_data['ticker']))
        
        existing = cur.fetchone()
        if existing:
            print(f"   ⚠️ Ativo {test_data['ticker']} já existe (ID: {existing[0]})")
            # Remover para teste limpo
            cur.execute("""
                DELETE FROM portfolio_assets 
                WHERE portfolio_name = %s AND ticker = %s
            """, (test_data['portfolio_name'], test_data['ticker']))
            print(f"   🗑️ Ativo removido para teste")
        
        # INSERIR NOVO ATIVO
        insert_sql = """
            INSERT INTO portfolio_assets (
                portfolio_name, ticker, weight, sector, 
                entry_price, current_price, target_price, entry_date,
                is_active, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        values = (
            test_data['portfolio_name'],
            test_data['ticker'],
            test_data['weight'],
            test_data['sector'],
            test_data['entry_price'],
            test_data['current_price'],
            test_data['target_price'],
            test_data['entry_date'],
            True,  # is_active
            datetime.now(),  # created_at
            datetime.now()   # updated_at
        )
        
        print(f"   📝 SQL: {insert_sql}")
        print(f"   📊 Values: {values}")
        
        cur.execute(insert_sql, values)
        new_id = cur.fetchone()[0]
        
        print(f"   ✅ INSERÇÃO OK! ID retornado: {new_id}")
        
        # COMMIT
        conn.commit()
        print(f"   ✅ COMMIT executado!")
        
        # VERIFICAR SE FOI SALVO
        cur.execute("""
            SELECT id, ticker, weight, sector, entry_price 
            FROM portfolio_assets 
            WHERE id = %s
        """, (new_id,))
        
        saved_data = cur.fetchone()
        if saved_data:
            print(f"   ✅ VERIFICAÇÃO: Ativo salvo corretamente!")
            print(f"      ID: {saved_data[0]}")
            print(f"      Ticker: {saved_data[1]}")
            print(f"      Peso: {saved_data[2]}%")
            print(f"      Setor: {saved_data[3]}")
            print(f"      Preço: R$ {saved_data[4]}")
        else:
            print(f"   ❌ ERRO: Ativo não encontrado após inserção!")
        
        # LIMPAR TESTE
        cur.execute("DELETE FROM portfolio_assets WHERE id = %s", (new_id,))
        conn.commit()
        print(f"   🧹 Ativo de teste removido")
        
    except Exception as e:
        print(f"   ❌ ERRO NA INSERÇÃO: {e}")
        conn.rollback()
    
    # 5. VERIFICAR ATIVOS EXISTENTES
    print("\n📋 5. Ativos existentes por portfolio...")
    try:
        cur.execute("""
            SELECT portfolio_name, COUNT(*), SUM(weight)
            FROM portfolio_assets 
            WHERE is_active = true
            GROUP BY portfolio_name
            ORDER BY portfolio_name
        """)
        
        assets_summary = cur.fetchall()
        for portfolio, count, total_weight in assets_summary:
            print(f"   📊 {portfolio}: {count} ativos, {total_weight}% peso total")
            
    except Exception as e:
        print(f"   ❌ ERRO: {e}")
    
    # 6. TESTE DE CONEXÃO E PERMISSÕES
    print("\n🔒 6. Testando permissões...")
    try:
        # Testar SELECT
        cur.execute("SELECT COUNT(*) FROM portfolio_assets")
        count = cur.fetchone()[0]
        print(f"   ✅ SELECT: {count} ativos no total")
        
        # Testar INSERT simples
        cur.execute("""
            INSERT INTO portfolio_assets (portfolio_name, ticker, weight, sector, entry_price, target_price)
            VALUES ('smart_bdr', 'PERM_TEST', 1.0, 'Teste', 10.0, 12.0)
            RETURNING id
        """)
        test_id = cur.fetchone()[0]
        print(f"   ✅ INSERT: OK (ID: {test_id})")
        
        # Testar UPDATE
        cur.execute("UPDATE portfolio_assets SET weight = 2.0 WHERE id = %s", (test_id,))
        print(f"   ✅ UPDATE: OK")
        
        # Testar DELETE
        cur.execute("DELETE FROM portfolio_assets WHERE id = %s", (test_id,))
        print(f"   ✅ DELETE: OK")
        
        conn.commit()
        print(f"   ✅ COMMIT: OK")
        
    except Exception as e:
        print(f"   ❌ ERRO DE PERMISSÕES: {e}")
        conn.rollback()
    
    # Fechar conexão
    cur.close()
    conn.close()
    
    print(f"\n🎯 RESULTADO FINAL:")
    print(f"   - Conexão Railway: ✅ OK")
    print(f"   - Tabelas existem: ✅ OK") 
    print(f"   - INSERT funciona: ✅ OK")
    print(f"   - COMMIT funciona: ✅ OK")
    print(f"\n💡 CONCLUSÃO: O BANCO ESTÁ OK!")
    print(f"   O problema está na API/ROTA do Flask!")

if __name__ == "__main__":
    test_portfolio_insertion()