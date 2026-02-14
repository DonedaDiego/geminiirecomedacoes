"""
Teste simples para verificar o cálculo do trial
Rode: python test_trial.py
"""
import psycopg2
from datetime import datetime
import os

# CONFIGURE AQUI
DB_CONFIG = {
    'host': 'ballast.proxy.rlwy.net',
    'database': 'railway',
    'user': 'postgres',
    'password': 'SWYYPTWLukrNVucLgnyImUfTftHSadyS',
    'port': 33654
}

EMAIL = 'diedoneda@gmail.com'

def test():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Buscar dados
    cur.execute("""
        SELECT 
            name,
            email,
            user_type,
            trial_end_date,
            created_at,
            NOW() as now,
            trial_end_date - NOW() as diff,
            EXTRACT(DAY FROM (trial_end_date - NOW())) as days_sql
        FROM users 
        WHERE email = %s
    """, (EMAIL,))
    
    row = cur.fetchone()
    
    if not row:
        print("❌ Usuário não encontrado!")
        return
    
    name, email, user_type, trial_end, created, now, diff, days_sql = row
    
    print("=" * 60)
    print(f"👤 {name} ({email})")
    print(f"📋 Tipo: {user_type}")
    print("=" * 60)
    print(f"🗓️  Trial End Date: {trial_end}")
    print(f"🗓️  Created At:     {created}")
    print(f"⏰ Now (DB):       {now}")
    print(f"📊 Diferença:      {diff}")
    print(f"🔢 Dias (SQL):     {days_sql}")
    print("=" * 60)
    
    # Calcular em Python
    now_py = datetime.now()
    if trial_end:
        diff_py = trial_end - now_py
        days_py = diff_py.days
        print(f"🐍 Now (Python):   {now_py}")
        print(f"🐍 Dias (Python):  {days_py}")
        print("=" * 60)
        
        # Comparar
        if days_sql and days_py != int(days_sql):
            print(f"⚠️  DIFERENÇA! SQL={int(days_sql)} vs Python={days_py}")
        else:
            print(f"✅ OK! Ambos calcularam {days_py} dias")
    else:
        print("⚠️  trial_end_date é NULL!")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    test()