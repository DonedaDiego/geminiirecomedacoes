#!/usr/bin/env python3
# importar_csv_local.py - Importa dados fundamentalistas do CSV para banco local PostgreSQL

import psycopg2
import csv
import os
from datetime import datetime
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def conectar_banco_local():
    """Conecta ao banco PostgreSQL local"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 5432)),
            dbname=os.getenv('DB_NAME', 'postgres'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', '#geminii')
        )
        print("✅ Conectado ao banco local PostgreSQL!")
        return conn
    except Exception as e:
        print(f"❌ Erro na conexão: {e}")
        return None

def criar_tabela_fundamentalista(conn):
    """Cria a tabela banco_fundamentalista no banco local"""
    try:
        cur = conn.cursor()
        
        # Drop da tabela se existir (para recriar)
        cur.execute("DROP TABLE IF EXISTS banco_fundamentalista")
        print("🗑️ Tabela existente removida (se havia)")
        
        # Criar tabela com todos os campos
        sql_create = """
        CREATE TABLE banco_fundamentalista (
            id SERIAL PRIMARY KEY,
            papel VARCHAR(10) NOT NULL,
            cotacao DECIMAL(10,2),
            p_l DECIMAL(10,2),
            p_vp DECIMAL(10,2),
            psr DECIMAL(10,3),
            div_yield VARCHAR(10),  -- Pode ter % no final
            p_ativo DECIMAL(10,3),
            p_cap_giro DECIMAL(10,2),
            p_ebit DECIMAL(10,2),
            p_ativ_circ_liq DECIMAL(10,2),
            ev_ebit DECIMAL(10,2),
            ev_ebitda DECIMAL(10,2),
            mrg_ebit VARCHAR(10),   -- Pode ter % no final
            mrg_liq VARCHAR(10),    -- Pode ter % no final
            liq_corr DECIMAL(10,2),
            roic VARCHAR(10),       -- Pode ter % no final
            roe VARCHAR(10),        -- Pode ter % no final
            liq_2meses VARCHAR(20), -- Pode ter formatação numérica especial
            patrim_liq VARCHAR(20), -- Valores grandes com formatação
            div_brut_patrim DECIMAL(10,2),
            cresc_rec_5a VARCHAR(10), -- Pode ter % no final
            data_importacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        cur.execute(sql_create)
        conn.commit()
        print("✅ Tabela 'banco_fundamentalista' criada com sucesso!")
        
        cur.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela: {e}")
        return False

def limpar_valor(valor):
    """Limpa e formata valores do CSV"""
    if not valor or valor.strip() == '' or valor.strip() == '-':
        return None
    
    # Remove espaços
    valor = valor.strip()
    
    # Se for um número puro, tenta converter
    try:
        # Remove pontos de milhares e substitui vírgula por ponto
        if ',' in valor and '.' in valor:
            # Formato brasileiro: 1.234.567,89
            valor = valor.replace('.', '').replace(',', '.')
        elif ',' in valor:
            # Só vírgula: 123,45
            valor = valor.replace(',', '.')
        
        # Tenta converter para float (só para validar)
        float(valor.replace('%', '').replace('R$', ''))
        return valor
    except:
        return valor

def importar_csv_para_local(caminho_csv):
    """Importa dados do CSV para o banco local"""
    
    if not os.path.exists(caminho_csv):
        print(f"❌ Arquivo CSV não encontrado: {caminho_csv}")
        return False
    
    # Conectar ao banco
    conn = conectar_banco_local()
    if not conn:
        return False
    
    # Criar tabela
    if not criar_tabela_fundamentalista(conn):
        conn.close()
        return False
    
    try:
        cur = conn.cursor()
        
        print(f"📁 Lendo arquivo: {caminho_csv}")
        
        # Ler CSV com diferentes encodings para tratar BOM
        encodings_to_try = ['utf-8-sig', 'utf-8', 'latin1', 'cp1252']
        
        for encoding in encodings_to_try:
            try:
                print(f"🔄 Tentando encoding: {encoding}")
                with open(caminho_csv, 'r', encoding=encoding) as arquivo:
                    # Detectar delimitador
                    sample = arquivo.read(1024)
                    arquivo.seek(0)
                    
                    # Tentar diferentes delimitadores
                    if '\t' in sample:
                        delimiter = '\t'
                        print("📌 Usando delimitador: TAB")
                    elif ';' in sample:
                        delimiter = ';'
                        print("📌 Usando delimitador: ;")
                    else:
                        delimiter = ','
                        print("📌 Usando delimitador: ,")
                    
                    reader = csv.DictReader(arquivo, delimiter=delimiter)
                    
                    # Verificar colunas detectadas
                    fieldnames = reader.fieldnames
                    print(f"🏷️ Colunas detectadas: {fieldnames}")
                    
                    # Limpar BOM das colunas se existir
                    fieldnames_clean = []
                    for col in fieldnames:
                        if col:
                            clean_col = col.replace('\ufeff', '').strip()
                            fieldnames_clean.append(clean_col)
                        else:
                            fieldnames_clean.append(col)
                    
                    print(f"🧹 Colunas após limpeza: {fieldnames_clean}")
                    
                    # Mapear colunas do CSV para campos da tabela
                    mapeamento_colunas = {
                        'Papel': 'papel',
                        'Cotação': 'cotacao',
                        'P/L': 'p_l',
                        'P/VP': 'p_vp',
                        'PSR': 'psr',
                        'Div.Yield': 'div_yield',
                        'P/Ativo': 'p_ativo',
                        'P/Cap.Giro': 'p_cap_giro',
                        'P/EBIT': 'p_ebit',
                        'P/Ativ Circ.Liq': 'p_ativ_circ_liq',
                        'EV/EBIT': 'ev_ebit',
                        'EV/EBITDA': 'ev_ebitda',
                        'Mrg Ebit': 'mrg_ebit',
                        'Mrg. Líq.': 'mrg_liq',
                        'Liq. Corr.': 'liq_corr',
                        'ROIC': 'roic',
                        'ROE': 'roe',
                        'Liq.2meses': 'liq_2meses',
                        'Patrim. Líq': 'patrim_liq',
                        'Dív.Brut/ Patrim.': 'div_brut_patrim',
                        'Cresc. Rec.5a': 'cresc_rec_5a'
                    }
                    
                    # Mapear colunas limpas para usar
                    mapeamento_real = {}
                    for col_original in fieldnames:
                        col_limpa = col_original.replace('\ufeff', '').strip() if col_original else ''
                        if col_limpa in mapeamento_colunas:
                            mapeamento_real[col_original] = mapeamento_colunas[col_limpa]
                    
                    print(f"🗺️ Mapeamento final: {mapeamento_real}")
                    break
            except Exception as e:
                print(f"❌ Erro com encoding {encoding}: {e}")
                if encoding == encodings_to_try[-1]:  # último encoding
                    raise
                continue
        
        with open(caminho_csv, 'r', encoding=encoding) as arquivo:
            reader = csv.DictReader(arquivo, delimiter=delimiter)
            
            print("🔄 Iniciando importação...")
            
            # SQL de inserção
            sql_insert = """
            INSERT INTO banco_fundamentalista (
                papel, cotacao, p_l, p_vp, psr, div_yield, p_ativo, p_cap_giro,
                p_ebit, p_ativ_circ_liq, ev_ebit, ev_ebitda, mrg_ebit, mrg_liq,
                liq_corr, roic, roe, liq_2meses, patrim_liq, div_brut_patrim, cresc_rec_5a
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """
            
            registros_inseridos = 0
            registros_erro = 0
            
            for linha in reader:
                try:
                    # Preparar dados para inserção
                    dados = []
                    papel_encontrado = False
                    
                    for coluna_csv, campo_db in mapeamento_real.items():
                        valor = linha.get(coluna_csv, '')
                        valor_limpo = limpar_valor(valor)
                        
                        # Debug do primeiro campo (papel)
                        if campo_db == 'papel':
                            if valor_limpo:
                                papel_encontrado = True
                                print(f"🔍 Papel encontrado: '{valor_limpo}' (original: '{valor}')")
                        
                        # Conversões específicas para campos numéricos
                        if campo_db in ['cotacao', 'p_l', 'p_vp', 'psr', 'p_ativo', 'p_cap_giro', 
                                       'p_ebit', 'p_ativ_circ_liq', 'ev_ebit', 'ev_ebitda', 
                                       'liq_corr', 'div_brut_patrim']:
                            try:
                                if valor_limpo:
                                    # Remove % se houver e converte
                                    valor_num = valor_limpo.replace('%', '').replace(',', '.')
                                    dados.append(float(valor_num) if valor_num != '' else None)
                                else:
                                    dados.append(None)
                            except:
                                dados.append(None)
                        else:
                            dados.append(valor_limpo)
                    
                    # Verificar se tem papel válido
                    if not papel_encontrado or not dados[0]:  # papel é o primeiro campo
                        print(f"⚠️ Linha sem papel válido, dados: {dados[:3]}...")
                        
                        # Debug da primeira linha problemática
                        if registros_inseridos == 0 and registros_erro == 0:
                            print(f"🔍 DEBUG primeira linha:")
                            print(f"   Linha completa: {dict(linha)}")
                            print(f"   Mapeamento usado: {mapeamento_real}")
                        
                        registros_erro += 1
                        continue
                    
                    # Inserir no banco
                    cur.execute(sql_insert, dados)
                    registros_inseridos += 1
                    
                    if registros_inseridos % 50 == 0:
                        print(f"📊 Inseridos {registros_inseridos} registros...")
                
                except Exception as e:
                    print(f"⚠️ Erro ao inserir linha: {e}")
                    registros_erro += 1
            
            # Commit final
            conn.commit()
            
            print(f"\n🎉 Importação concluída!")
            print(f"📈 Registros inseridos: {registros_inseridos}")
            print(f"❌ Registros com erro: {registros_erro}")
            
            # Mostrar alguns registros inseridos
            cur.execute("SELECT papel, cotacao, roic, ev_ebit FROM banco_fundamentalista LIMIT 5")
            print(f"\n📋 Primeiros 5 registros inseridos:")
            for row in cur.fetchall():
                print(f"   {row[0]} - Cotação: {row[1]} - ROIC: {row[2]} - EV/EBIT: {row[3]}")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro durante importação: {e}")
        conn.close()
        return False

def verificar_importacao():
    """Verifica os dados importados no banco local"""
    conn = conectar_banco_local()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # Total de registros
        cur.execute("SELECT COUNT(*) FROM banco_fundamentalista")
        total = cur.fetchone()[0]
        print(f"\n📊 Total de registros na tabela: {total}")
        
        # Alguns exemplos com ROIC válido
        cur.execute("""
            SELECT papel, cotacao, roic, ev_ebit 
            FROM banco_fundamentalista 
            WHERE roic IS NOT NULL 
            AND roic != ''
            AND roic != '-'
            ORDER BY papel 
            LIMIT 10
        """)
        
        print(f"\n🔍 Amostra dos dados (ROIC não nulo):")
        for row in cur.fetchall():
            print(f"   {row[0]}: Cotação={row[1]}, ROIC={row[2]}, EV/EBIT={row[3]}")
        
        # Estatísticas de dados válidos
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN roic IS NOT NULL AND roic != '' AND roic != '-' THEN 1 END) as roic_validos,
                COUNT(CASE WHEN ev_ebit IS NOT NULL AND ev_ebit != '' AND ev_ebit != '-' THEN 1 END) as ev_ebit_validos
            FROM banco_fundamentalista
        """)
        
        stats = cur.fetchone()
        print(f"\n📈 Estatísticas:")
        print(f"   Total de empresas: {stats[0]}")
        print(f"   Com ROIC válido: {stats[1]}")
        print(f"   Com EV/EBIT válido: {stats[2]}")
        print(f"   Dados completos: {min(stats[1], stats[2])}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro na verificação: {e}")

def testar_formula_magica():
    """Testa se a Fórmula Mágica pode ser calculada com os dados"""
    conn = conectar_banco_local()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        print(f"\n🧮 Testando cálculo da Fórmula Mágica...")
        
        # Query similar à do serviço
        cur.execute("""
            SELECT 
                papel,
                cotacao,
                roic,
                ev_ebit
            FROM banco_fundamentalista
            WHERE papel IS NOT NULL 
            AND cotacao IS NOT NULL
            AND roic IS NOT NULL AND roic != '' AND roic != '-'
            AND ev_ebit IS NOT NULL AND ev_ebit != '' AND ev_ebit != '-'
            ORDER BY papel
            LIMIT 5
        """)
        
        resultados = cur.fetchall()
        print(f"✅ {len(resultados)} empresas prontas para Fórmula Mágica:")
        
        for row in resultados:
            papel, cotacao, roic, ev_ebit = row
            print(f"   {papel}: Cotação={cotacao}, ROIC={roic}, EV/EBIT={ev_ebit}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")

if __name__ == "__main__":
    # Caminho do CSV (ajuste conforme necessário)
    caminho_csv = r"C:\Users\usuario\Desktop\Bases Fundamentalistas\base_fundamentalista_railway.csv"
    
    print("🚀 INICIANDO IMPORTAÇÃO PARA BANCO LOCAL")
    print("=" * 60)
    print(f"📍 Banco: {os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
    print(f"👤 Usuário: {os.getenv('DB_USER')}")
    print(f"📁 Arquivo: {caminho_csv}")
    print("=" * 60)
    
    if importar_csv_para_local(caminho_csv):
        print("\n🎉 PROCESSO CONCLUÍDO COM SUCESSO!")
        verificar_importacao()
        testar_formula_magica()
    else:
        print("\n💥 PROCESSO FALHOU!")
        
    print("\n🔧 Próximos passos:")
    print("1. Verifique se o serviço formula_service.py está configurado")
    print("2. Teste os endpoints em /api/formula/")
    print("3. Acesse formula.html para ver a interface")