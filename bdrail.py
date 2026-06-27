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
            plan_name,
            subscription_status,
            plan_expires_at,
            created_at,
            registration_date,
            last_login,
            NOW() as now,
            plan_expires_at - NOW() as diff,
            EXTRACT(DAY FROM (plan_expires_at - NOW())) as days_sql
        FROM users 
        WHERE email = %s
    """, (EMAIL,))
    
    row = cur.fetchone()
    
    if not row:
        print("❌ Usuário não encontrado!")
        return
    
    name, email, user_type, plan_name, sub_status, plan_expires, created, reg_date, last_login, now, diff, days_sql = row
    
    print("=" * 60)
    print(f"👤 {name} ({email})")
    print(f"📋 User Type: {user_type}")
    print(f"💳 Plan Name: {plan_name}")
    print(f" Status: {sub_status}")
    print("=" * 60)
    print(f"🗓️  Plan Expires At: {plan_expires}")
    print(f"🗓️  Created At:      {created}")
    print(f"🗓️  Registration:    {reg_date}")
    print(f"🗓️  Last Login:      {last_login}")
    print(f" Now (DB):        {now}")
    print(f" Diferença:       {diff}")
    print(f"🔢 Dias (SQL):      {days_sql}")
    print("=" * 60)
    
    # Calcular em Python
    now_py = datetime.now()
    if plan_expires:
        diff_py = plan_expires - now_py
        days_py = diff_py.days
        print(f"🐍 Now (Python):    {now_py}")
        print(f"🐍 Dias (Python):   {days_py}")
        print("=" * 60)
        
        # Comparar
        if days_sql is not None and days_py != int(days_sql):
            print(f"  DIFERENÇA! SQL={int(days_sql)} vs Python={days_py}")
        else:
            print(f" OK! Ambos calcularam {days_py} dias")
            
        # Status do plano
        if days_py < 0:
            print(f"🚨 PLANO EXPIRADO há {abs(days_py)} dias!")
        elif days_py < 5:
            print(f" ATENÇÃO: Plano expira em {days_py} dias!")
        else:
            print(f" Plano ativo com {days_py} dias restantes")
    else:
        print("  plan_expires_at é NULL!")
        print("💡 Sugestão: Verificar se o trial foi configurado corretamente")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    test()