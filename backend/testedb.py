# testedb.py - VERIFICAÇÃO FINAL
import psycopg2
import os
from datetime import datetime, timezone

def force_update_last_login():
    """Forçar atualização do last_login"""
    try:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            conn = psycopg2.connect(
                host="localhost", database="postgres", 
                user="postgres", password="#geminii", port="5432"
            )
        else:
            conn = psycopg2.connect(database_url)
        
        cursor = conn.cursor()
        
        print("=== FORÇANDO UPDATE DO LAST_LOGIN ===")
        
        # Atualizar manualmente
        now = datetime.now(timezone.utc)
        cursor.execute("""
            UPDATE users 
            SET last_login = %s, updated_at = %s
            WHERE email = 'diego@geminii.com.br'
        """, (now, now))
        
        print(f"Rows affected: {cursor.rowcount}")
        conn.commit()
        print("Commit executado!")
        
        # Verificar se foi atualizado
        cursor.execute("SELECT last_login FROM users WHERE email = 'diego@geminii.com.br'")
        new_login = cursor.fetchone()[0]
        print(f"Novo last_login: {new_login}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"Erro: {e}")
        return False

if __name__ == "__main__":
    force_update_last_login()