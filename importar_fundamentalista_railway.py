#!/usr/bin/env python3
# importar_fundamentalista_railway.py - Importa dados fundamentalistas do CSV para Railway

import psycopg2
import csv
import os
from datetime import datetime

def conectar_railway():
    """Conecta ao banco Railway"""
    try:
        conn = psycopg2.connect(
            host="ballast.proxy.rlwy.net",
            port=33654,
            dbname="railway",
            user="postgres",
            password="SWYYPTWLukrNVucLgnyImUfTftHSadyS"
        )
        return conn
    except Exception as e:
        print(f"❌ Erro na conexão: {e}")
        return None

def criar_tabela_fundamentalista(conn):
    """Cria a tabela banco_fundamentalista"""
    try:
        cur = conn.cursor()
        
        # Drop da tabela se existir (para recriar)
        cur.execute("DROP TABLE IF EXISTS banco_fundamentalista")
        
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
        
        # Tenta converter para float
        float(valor.replace('%', '').replace('R$', ''))
        return valor
    except:
        return valor

def importar_csv_para_railway(caminho_csv):
    """Importa dados do CSV para o Railway"""
    
    if not os.path.exists(caminho_csv):
        print(f"❌ Arquivo CSV não encontrado: {caminho_csv}")
        return False
    
    # Conectar ao banco
    conn = conectar_railway()
    if not conn:
        return False
    
    # Criar tabela
    if not criar_tabela_fundamentalista(conn):
        conn.close()
        return False
    
    try:
        cur = conn.cursor()
        
        # Primeiro, vamos inspecionar o arquivo para entender o formato
        print("🔍 Inspecionando arquivo CSV...")
        with open(caminho_csv, 'r', encoding='utf-8') as arquivo:
            primeiras_linhas = [arquivo.readline().strip() for _ in range(3)]
            print("📋 Primeiras 3 linhas do arquivo:")
            for i, linha in enumerate(primeiras_linhas):
                print(f"   Linha {i+1}: {linha[:100]}...")
        
        # Ler CSV com diferentes tentativas
        with open(caminho_csv, 'r', encoding='utf-8') as arquivo:
            # Detectar delimitador
            primeira_linha = arquivo.readline()
            arquivo.seek(0)
            
            print(f"🔍 Primeira linha: {primeira_linha}")
            
            # Tentar diferentes delimitadores baseado no conteúdo
            if primeira_linha.count('\t') > primeira_linha.count(','):
                delimiter = '\t'
                print("📌 Usando delimitador: TAB")
            elif primeira_linha.count(';') > primeira_linha.count(','):
                delimiter = ';'
                print("📌 Usando delimitador: ;")
            else:
                delimiter = ','
                print("📌 Usando delimitador: ,")
            
            reader = csv.DictReader(arquivo, delimiter=delimiter)
            
            # Verificar se conseguiu ler o cabeçalho
            fieldnames = reader.fieldnames
            print(f"🏷️ Colunas detectadas: {fieldnames}")
            
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
            
            # Se não encontrou as colunas esperadas, tentar mapear automaticamente
            if not fieldnames or 'Papel' not in fieldnames:
                print("⚠️ Colunas esperadas não encontradas. Tentando mapeamento automático...")
                
                # Tentar encontrar colunas similares
                possible_papel_cols = [col for col in fieldnames if col and ('papel' in col.lower() or len(col.strip()) <= 6)]
                if possible_papel_cols:
                    print(f"🎯 Possíveis colunas para 'Papel': {possible_papel_cols}")
            
            linha_count = 0
            for linha in reader:
                linha_count += 1
                try:
                    # Debug da primeira linha para entender o formato
                    if linha_count == 1:
                        print(f"🔍 Primeira linha de dados: {dict(linha)}")
                    
                    # Preparar dados para inserção
                    dados = []
                    
                    # Tentar pegar o papel (primeira coluna mais provável)
                    papel_valor = None
                    for key, value in linha.items():
                        if value and len(str(value).strip()) <= 10 and str(value).strip().isalnum():
                            papel_valor = str(value).strip()
                            break
                    
                    if not papel_valor:
                        print(f"⚠️ Linha {linha_count}: Papel não encontrado, pulando...")
                        continue
                    
                    # Adicionar rollback em caso de erro
                    savepoint = f"sp_{linha_count}"
                    cur.execute(f"SAVEPOINT {savepoint}")
                    
                    for coluna_csv, campo_db in mapeamento_colunas.items():
                        if campo_db == 'papel':
                            dados.append(papel_valor)
                        else:
                            valor = linha.get(coluna_csv, '')
                            valor_limpo = limpar_valor(valor)
                            
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
                    
                    # Inserir no banco
                    cur.execute(sql_insert, dados)
                    cur.execute(f"RELEASE SAVEPOINT {savepoint}")
                    registros_inseridos += 1
                    
                    if registros_inseridos % 10 == 0:
                        print(f"📊 Inseridos {registros_inseridos} registros...")
                
                except Exception as e:
                    cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    cur.execute(f"RELEASE SAVEPOINT {savepoint}")
                    print(f"⚠️ Erro ao inserir linha {linha_count} (Papel: {papel_valor}): {e}")
                    registros_erro += 1
                    
                    # Se muitos erros, parar
                    if registros_erro > 10 and registros_inseridos == 0:
                        print("❌ Muitos erros sequenciais. Parando importação.")
                        break
            
            # Commit final
            conn.commit()
            
            print(f"\n✅ Importação concluída!")
            print(f"📈 Registros inseridos: {registros_inseridos}")
            print(f"❌ Registros com erro: {registros_erro}")
            
            # Mostrar alguns registros inseridos
            cur.execute("SELECT papel, cotacao, roic, ev_ebit FROM banco_fundamentalista LIMIT 5")
            print(f"\n📋 Primeiros registros inseridos:")
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
    """Verifica os dados importados"""
    conn = conectar_railway()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # Total de registros
        cur.execute("SELECT COUNT(*) FROM banco_fundamentalista")
        total = cur.fetchone()[0]
        print(f"\n📊 Total de registros na tabela: {total}")
        
        # Alguns exemplos
        cur.execute("""
            SELECT papel, cotacao, roic, ev_ebit 
            FROM banco_fundamentalista 
            WHERE roic IS NOT NULL 
            ORDER BY papel 
            LIMIT 10
        """)
        
        print(f"\n🔍 Amostra dos dados (ROIC não nulo):")
        for row in cur.fetchall():
            print(f"   {row[0]}: Cotação={row[1]}, ROIC={row[2]}, EV/EBIT={row[3]}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro na verificação: {e}")

if __name__ == "__main__":
    caminho_csv = r"C:\Users\usuario\Desktop\Bases Fundamentalistas\base_fundamentalista_railway.csv"
    
    print("🚀 Iniciando importação da base fundamentalista...")
    print(f"📁 Arquivo: {caminho_csv}")
    
    if importar_csv_para_railway(caminho_csv):
        print("\n🎉 Processo concluído com sucesso!")
        verificar_importacao()
    else:
        print("\n💥 Falha na importação!")