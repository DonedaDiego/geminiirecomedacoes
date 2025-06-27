##testa coneção

# import psycopg2

# try:
#     conn = psycopg2.connect(
#         host="ballast.proxy.rlwy.net",
#         port=33654,
#         dbname="railway",
#         user="postgres",
#         password="SWYYPTWLukrNVucLgnyImUfTftHSadyS"
#     )
#     print("✅ Conectado com sucesso!")
#     conn.close()

# except Exception as e:
#     print("❌ Erro ao conectar:")
#     print(repr(e))


# ## verifica as tabelas dentro 
# import psycopg2

# conn = psycopg2.connect(
#     host="ballast.proxy.rlwy.net",
#     port=33654,
#     dbname="railway",
#     user="postgres",
#     password="SWYYPTWLukrNVucLgnyImUfTftHSadyS"
# )

# cur = conn.cursor()

# # Consulta todas as tabelas do esquema 'public'
# cur.execute("""
#     SELECT table_name
#     FROM information_schema.tables
#     WHERE table_schema = 'public'
# """)

# print("🗂 Tabelas encontradas:")
# for table in cur.fetchall():
#     print(f" - {table[0]}")

# cur.close()
# conn.close()

###verifica as coluns dentro das tabelas
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
