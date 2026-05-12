import duckdb
DATA_DIR = r"C:\Users\Diego\Desktop\VSCode\dadoscvm"
con = duckdb.connect(f"{DATA_DIR}/dados_dfp.duckdb", read_only=True)

# valores exatos gravados no banco
print(con.execute("SELECT DISTINCT tipo_dem, ordem_exerc, con_ind FROM dados_dfp LIMIT 10").fetchall())
con.close()