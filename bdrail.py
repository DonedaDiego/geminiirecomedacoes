#!/usr/bin/env python3
# listar_railway.py - Lista todas as tabelas e colunas no banco Railway

import psycopg2

def listar_tabelas_e_colunas():
    try:
        conn = psycopg2.connect(
            host="ballast.proxy.rlwy.net",
            port=33654,
            dbname="railway",
            user="postgres",
            password="SWYYPTWLukrNVucLgnyImUfTftHSadyS"
        )
        cur = conn.cursor()
        print(" Conectado ao Railway!")

        # Buscar todas as tabelas no schema public
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tabelas = [row[0] for row in cur.fetchall()]

        for tabela in tabelas:
            print(f"\n🗂️ Tabela: {tabela}")
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (tabela,))
            colunas = cur.fetchall()
            for nome, tipo, nulo in colunas:
                print(f"   - {nome} ({tipo}) {'NULL' if nulo == 'YES' else 'NOT NULL'}")

        cur.close()
        conn.close()
        print("\n Finalizado com sucesso!")

    except Exception as e:
        print(f" Erro: {e}")

if __name__ == "__main__":
    listar_tabelas_e_colunas()
