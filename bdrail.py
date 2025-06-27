import psycopg2

conn = psycopg2.connect(
    host="ballast.proxy.rlwy.net",
    port=33654,
    dbname="railway",
    user="postgres",
    password="SWYYPTWLukrNVucLgnyImUfTftHSadyS"
)

cur = conn.cursor()

# Buscar todas as tabelas do schema público
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
""")

tables = cur.fetchall()

print("📘 Estrutura completa do banco:\n")

for (table,) in tables:
    print(f"📂 Tabela: {table}")
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = %s
    """, (table,))
    columns = cur.fetchall()
    for col_name, col_type in columns:
        print(f"   └── {col_name} ({col_type})")

cur.close()
conn.close()
