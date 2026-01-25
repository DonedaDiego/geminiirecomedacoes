# test_screening_table.py
from database import create_screening_cache_table, get_db_connection

print("🔧 Criando tabela screening_cache...")
success = create_screening_cache_table()

if success:
    print("✅ Tabela criada!")
    
    # Verificar se existe
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'screening_cache'
        ORDER BY ordinal_position
    """)
    
    print("\n📋 Colunas da tabela:")
    for col in cursor.fetchall():
        print(f"   - {col[0]}: {col[1]}")
    
    cursor.close()
    conn.close()
else:
    print("❌ Falha ao criar tabela")