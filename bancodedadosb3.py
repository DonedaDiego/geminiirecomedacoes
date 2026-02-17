#!/usr/bin/env python3
# criar_tabela_railway.py - Cria tabela opcoes_b3 vazia no Railway

import psycopg2

def criar_tabela_opcoes_b3():
    try:
        # CONECTA AO RAILWAY
        conn = psycopg2.connect(
            host="ballast.proxy.rlwy.net",
            port=33654,
            dbname="railway",
            user="postgres",
            password="SWYYPTWLukrNVucLgnyImUfTftHSadyS"
        )
        cur = conn.cursor()
        print(" Conectado ao Railway!")
        
        # VERIFICA SE TABELA JÁ EXISTE
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'opcoes_b3'
            )
        """)
        existe = cur.fetchone()[0]
        
        if existe:
            print("  Tabela opcoes_b3 já existe!")
            opcao = input("Apagar e recriar? (SIM/nao): ").strip().upper()
            
            if opcao == "SIM":
                cur.execute("DROP TABLE opcoes_b3")
                conn.commit()
                print("🗑️  Tabela antiga apagada")
            else:
                print("❌ Operação cancelada")
                cur.close()
                conn.close()
                return
        
        # CRIA A TABELA
        print("\n🏗️  Criando tabela opcoes_b3...")
        
        cur.execute("""
            CREATE TABLE opcoes_b3 (
                id SERIAL PRIMARY KEY,
                serie VARCHAR(50),
                preco_exercicio FLOAT,
                empresa VARCHAR(200),
                qtd_coberto FLOAT,
                qtd_descoberto FLOAT,
                clientes_titular FLOAT,
                qtd_trava FLOAT,
                qtd_total FLOAT,
                clientes_lancador FLOAT,
                vencimento_original VARCHAR(50),
                tipo_mercado VARCHAR(50),
                mercado VARCHAR(50),
                especie_papel VARCHAR(50),
                data_referencia DATE,
                tipo_opcao VARCHAR(10),
                vencimento DATE,
                ticker VARCHAR(20)
            )
        """)
        
        conn.commit()
        print(" Tabela opcoes_b3 criada com sucesso!")
        
        # LISTA AS COLUNAS CRIADAS
        print("\n📋 Estrutura da tabela:")
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'opcoes_b3'
            ORDER BY ordinal_position
        """)
        
        colunas = cur.fetchall()
        for nome, tipo, nulo in colunas:
            print(f"   - {nome} ({tipo}) {'NULL' if nulo == 'YES' else 'NOT NULL'}")
        
        # CONTA REGISTROS (deve ser 0)
        cur.execute("SELECT COUNT(*) FROM opcoes_b3")
        total = cur.fetchone()[0]
        print(f"\n Total de registros: {total}")
        
        cur.close()
        conn.close()
        print("\n Tudo pronto! Tabela vazia criada no Railway")

    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    criar_tabela_opcoes_b3()