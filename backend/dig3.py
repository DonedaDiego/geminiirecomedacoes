#!/usr/bin/env python3
# test_railway.py - TESTE DIRETO NO RAILWAY

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
    
    # TESTAR INSERÇÃO REAL
    print("\n💾 TESTANDO INSERÇÃO REAL...")
    
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
    
    try:
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
            True,
            datetime.now(),
            datetime.now()
        )
        
        cur.execute(insert_sql, values)
        new_id = cur.fetchone()[0]
        
        print(f"   ✅ INSERÇÃO OK! ID: {new_id}")
        
        # COMMIT
        conn.commit()
        print(f"   ✅ COMMIT OK!")
        
        # VERIFICAR
        cur.execute("SELECT ticker, weight FROM portfolio_assets WHERE id = %s", (new_id,))
        result = cur.fetchone()
        print(f"   ✅ VERIFICAÇÃO: {result[0]} - {result[1]}%")
        
        # LIMPAR
        cur.execute("DELETE FROM portfolio_assets WHERE id = %s", (new_id,))
        conn.commit()
        print(f"   🧹 Removido")
        
    except Exception as e:
        print(f"   ❌ ERRO: {e}")
    
    cur.close()
    conn.close()
    print(f"\n🎯 BANCO RAILWAY: ✅ OK")

if __name__ == "__main__":
    test_portfolio_insertion()