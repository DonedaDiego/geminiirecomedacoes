#!/usr/bin/env python3
# sync_railway_to_local.py - Sincronizar Railway para ficar igual ao Local

import psycopg2
import os

def get_local_structure():
    """Pegar estrutura da tabela local"""
    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            database=os.environ.get("DB_NAME", "postgres"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD", "#geminii"),
            port=os.environ.get("DB_PORT", "5432")
        )
        cursor = conn.cursor()
        print("✅ Conectado ao banco LOCAL")
        
        # Buscar estrutura da tabela local
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'coupons'
            ORDER BY ordinal_position
        """)
        local_columns = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return local_columns
        
    except Exception as e:
        print(f"❌ Erro ao conectar no LOCAL: {e}")
        return None

def sync_railway_to_local():
    """Ajustar Railway para ficar igual ao Local"""
    try:
        # 1. PEGAR ESTRUTURA LOCAL
        print("📋 Analisando estrutura LOCAL...")
        local_structure = get_local_structure()
        
        if not local_structure:
            print("❌ Não foi possível ler estrutura local")
            return False
        
        print("✅ Estrutura LOCAL:")
        local_columns = []
        for col_name, data_type, is_nullable, default in local_structure:
            local_columns.append(col_name)
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            print(f"   - {col_name:<20} {data_type:<15} {nullable:<10} {default or ''}")
        
        # 2. CONECTAR NO RAILWAY
        conn = psycopg2.connect(
            host="ballast.proxy.rlwy.net",
            port=33654,
            dbname="railway",
            user="postgres",
            password="SWYYPTWLukrNVucLgnyImUfTftHSadyS"
        )
        cursor = conn.cursor()
        print("\n✅ Conectado ao RAILWAY")
        
        # 3. VERIFICAR ESTRUTURA RAILWAY ATUAL
        print("\n📋 Analisando estrutura RAILWAY atual...")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'coupons'
            ORDER BY ordinal_position
        """)
        railway_structure = cursor.fetchall()
        
        railway_columns = []
        for col_name, data_type, is_nullable, default in railway_structure:
            railway_columns.append(col_name)
        
        print("✅ Estrutura RAILWAY atual:")
        for col_name, data_type, is_nullable, default in railway_structure:
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            print(f"   - {col_name:<20} {data_type:<15} {nullable:<10} {default or ''}")
        
        # 4. COMPARAR E AJUSTAR
        print(f"\n🔧 SINCRONIZANDO RAILWAY COM LOCAL...")
        
        # Colunas que existem no Railway mas não no Local (REMOVER)
        railway_only = set(railway_columns) - set(local_columns)
        if railway_only:
            print(f"\n❌ Colunas a REMOVER do Railway:")
            for col in railway_only:
                print(f"   - {col}")
                
                # CONFIRMAR ANTES DE REMOVER
                resposta = input(f"   ⚠️ REMOVER coluna '{col}' do Railway? (s/N): ").strip().lower()
                if resposta == 's':
                    try:
                        cursor.execute(f"ALTER TABLE coupons DROP COLUMN {col}")
                        print(f"   ✅ Coluna '{col}' removida")
                    except Exception as e:
                        print(f"   ❌ Erro ao remover '{col}': {e}")
                else:
                    print(f"   ⏭️ Mantendo coluna '{col}'")
        
        # Colunas que existem no Local mas não no Railway (ADICIONAR)
        local_only = set(local_columns) - set(railway_columns)
        if local_only:
            print(f"\n✅ Colunas a ADICIONAR no Railway:")
            for col in local_only:
                # Encontrar definição no local
                col_def = None
                for local_col in local_structure:
                    if local_col[0] == col:
                        col_name, data_type, is_nullable, default = local_col
                        
                        # Mapear tipos PostgreSQL
                        type_mapping = {
                            'character varying': 'VARCHAR(255)',
                            'integer': 'INTEGER',
                            'numeric': 'NUMERIC',
                            'boolean': 'BOOLEAN',
                            'timestamp without time zone': 'TIMESTAMP',
                            'ARRAY': 'TEXT[]'
                        }
                        
                        pg_type = type_mapping.get(data_type, data_type)
                        nullable_clause = "" if is_nullable == "YES" else "NOT NULL"
                        default_clause = f"DEFAULT {default}" if default else ""
                        
                        col_def = f"{pg_type} {nullable_clause} {default_clause}".strip()
                        break
                
                if col_def:
                    print(f"   + {col}: {col_def}")
                    try:
                        cursor.execute(f"ALTER TABLE coupons ADD COLUMN {col} {col_def}")
                        print(f"   ✅ Coluna '{col}' adicionada")
                    except Exception as e:
                        print(f"   ❌ Erro ao adicionar '{col}': {e}")
        
        # 5. VERIFICAR RESULTADO
        print(f"\n🔍 VERIFICANDO RESULTADO...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'coupons'
            ORDER BY ordinal_position
        """)
        final_columns = [row[0] for row in cursor.fetchall()]
        
        print("✅ Estrutura FINAL do Railway:")
        for col in final_columns:
            status = "✅" if col in local_columns else "⚠️"
            print(f"   {status} {col}")
        
        # Confirmar mudanças
        resposta = input(f"\n💾 SALVAR todas as mudanças? (s/N): ").strip().lower()
        if resposta == 's':
            conn.commit()
            print("✅ Mudanças salvas no Railway!")
        else:
            conn.rollback()
            print("❌ Mudanças descartadas")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔄 SINCRONIZANDO RAILWAY COM LOCAL")
    print("="*50)
    print("⚠️ ATENÇÃO: Este script vai ajustar a tabela 'coupons' do Railway")
    print("   para ficar IDÊNTICA à estrutura local!")
    print()
    
    resposta = input("🤔 Continuar? (s/N): ").strip().lower()
    if resposta != 's':
        print("❌ Operação cancelada")
        exit()
    
    if sync_railway_to_local():
        print("\n🎉 Sincronização concluída!")
        print("   Agora o Railway tem a mesma estrutura do Local")
    else:
        print("\n❌ Sincronização falhou!")