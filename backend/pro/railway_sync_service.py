# railway_sync_service.py - Sincroniza dados B3 → Railway

import requests
import pandas as pd
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine, text
import logging
from typing import Dict, List, Optional


class RailwaySyncService:
    def __init__(self):
        self.RAILWAY_HOST = "ballast.proxy.rlwy.net"
        self.RAILWAY_PORT = "33654"
        self.RAILWAY_USER = "postgres"
        self.RAILWAY_PASSWORD = "SWYYPTWLukrNVucLgnyImUfTftHSadyS"
        self.RAILWAY_DATABASE = "railway"

        self.DATABASE_URL = f"postgresql://{self.RAILWAY_USER}:{self.RAILWAY_PASSWORD}@{self.RAILWAY_HOST}:{self.RAILWAY_PORT}/{self.RAILWAY_DATABASE}"
        self.engine = create_engine(self.DATABASE_URL)

        self.setup_logging()
        self.garantir_estrutura()

    def setup_logging(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def garantir_estrutura(self):
        """Garante que coluna ticker existe"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("""
                    ALTER TABLE opcoes_b3 
                    ADD COLUMN IF NOT EXISTS ticker VARCHAR(20)
                """))
                conn.commit()
                self.logger.info("✅ Estrutura verificada")
        except Exception as e:
            self.logger.warning(f"⚠️ Estrutura: {e}")

    def verificar_data_existe(self, data_obj: datetime) -> bool:
        """Verifica se data já existe no banco"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT COUNT(*) as total
                    FROM opcoes_b3
                    WHERE data_referencia = :data_ref
                """), {"data_ref": data_obj})

                count = result.fetchone()[0]
                return count > 0
        except Exception as e:
            self.logger.error(f"❌ Erro ao verificar data: {e}")
            return False

    def baixar_json_b3(self, data_obj: datetime) -> Optional[Dict]:
        """Baixa JSON da B3"""
        folder_date = data_obj.strftime('%Y%m%d')
        url = f"https://www.b3.com.br/json/{folder_date}/Posicoes/Empresa/SI_C_OPCPOSABEMP.json"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        try:
            # ✅ Timeout reduzido para 10s — falha rápido, não trava o worker
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                self.logger.info(f"✅ Download OK: {folder_date}")
                return response.json()
            else:
                self.logger.warning(f"⚠️ HTTP {response.status_code}: {folder_date}")
                return None

        except Exception as e:
            self.logger.error(f"❌ Erro download {folder_date}: {e}")
            return None

    def processar_json(self, data_json: Dict, data_obj: datetime) -> pd.DataFrame:
        """Processa JSON em DataFrame"""
        all_opcoes = []

        for letra, empresas in data_json['Empresa'].items():
            if empresas:
                for opcao in empresas:
                    opcao['data_referencia'] = data_obj
                    opcao['tipo_opcao'] = 'CALL' if opcao.get('tMerc') == '70' else 'PUT'
                    opcao['vencimento'] = pd.to_datetime(opcao['dtVen'], format='%Y%m%d')

                    mer = opcao.get('mer', '')
                    esp = opcao.get('espPap', '')

                    if 'ON' in esp:
                        ticker = f"{mer}3"
                    elif 'PN' in esp:
                        ticker = f"{mer}4"
                    elif 'UNIT' in esp or 'UNT' in esp or 'CI' in esp:
                        ticker = f"{mer}11"
                    elif 'DRN' in esp or 'BDR' in esp:
                        ticker = f"{mer}34"
                    else:
                        ticker = mer

                    opcao['ticker'] = ticker
                    all_opcoes.append(opcao)

        df = pd.DataFrame(all_opcoes)

        df.rename(columns={
            'ser': 'serie',
            'prEx': 'preco_exercicio',
            'nmEmp': 'empresa',
            'poCob': 'qtd_coberto',
            'posDe': 'qtd_descoberto',
            'posTr': 'qtd_trava',
            'posTo': 'qtd_total',
            'qtdClTit': 'clientes_titular',
            'qtdClLan': 'clientes_lancador',
            'dtVen': 'vencimento_original',
            'tMerc': 'tipo_mercado',
            'mer': 'mercado',
            'espPap': 'especie_papel'
        }, inplace=True)

        df['preco_exercicio'] = pd.to_numeric(df['preco_exercicio'], errors='coerce')
        df['tipo_opcao'] = df['tipo_opcao'].astype(str)
        df['qtd_total'] = pd.to_numeric(df['qtd_total'], errors='coerce').fillna(0).astype(int)
        df['qtd_descoberto'] = pd.to_numeric(df['qtd_descoberto'], errors='coerce').fillna(0).astype(int)
        df['qtd_trava'] = pd.to_numeric(df['qtd_trava'], errors='coerce').fillna(0).astype(int)
        df['qtd_coberto'] = pd.to_numeric(df['qtd_coberto'], errors='coerce').fillna(0).astype(int)

        self.logger.info(f"✅ Processados: {len(df)} registros")
        return df

    def salvar_no_railway(self, df: pd.DataFrame) -> bool:
        """Salva DataFrame no Railway"""
        try:
            df.to_sql('opcoes_b3', self.engine, if_exists='append', index=False)
            self.logger.info(f"💾 Salvos {len(df)} registros")
            return True
        except Exception as e:
            self.logger.error(f"❌ Erro ao salvar: {e}")
            return False

    def sincronizar_datas(self, datas: List[str]) -> Dict:
        """Sincroniza lista de datas"""
        total_sucesso = 0
        total_falhas = 0
        total_pulados = 0
        detalhes = []

        for i, data_str in enumerate(datas, 1):
            data_obj = datetime.strptime(data_str, '%Y%m%d')
            data_formatada = data_obj.strftime('%d/%m/%Y')

            self.logger.info(f"[{i}/{len(datas)}] {data_formatada}")

            if self.verificar_data_existe(data_obj):
                self.logger.info(f"⏭️  Já existe, pulando...")
                total_pulados += 1
                detalhes.append({
                    "data": data_formatada,
                    "status": "pulado",
                    "motivo": "Já existe no banco"
                })
                continue

            json_data = self.baixar_json_b3(data_obj)

            if json_data:
                df = self.processar_json(json_data, data_obj)

                if self.salvar_no_railway(df):
                    self.logger.info(f"✅ SUCESSO!")
                    total_sucesso += 1
                    detalhes.append({
                        "data": data_formatada,
                        "status": "sucesso",
                        "registros": len(df)
                    })
                else:
                    total_falhas += 1
                    detalhes.append({
                        "data": data_formatada,
                        "status": "falha",
                        "motivo": "Erro ao salvar"
                    })
            else:
                self.logger.warning(f"❌ FALHA - JSON não disponível")
                total_falhas += 1
                detalhes.append({
                    "data": data_formatada,
                    "status": "falha",
                    "motivo": "JSON não disponível na B3"
                })

        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM opcoes_b3"))
            total_registros = result.fetchone()[0]

            result = conn.execute(text("""
                SELECT ticker, COUNT(*) as total
                FROM opcoes_b3
                WHERE ticker IS NOT NULL
                GROUP BY ticker
                ORDER BY total DESC
                LIMIT 5
            """))
            top_tickers = [{"ticker": row[0], "count": row[1]} for row in result]

        return {
            "resumo": {
                "total_datas": len(datas),
                "sucesso": total_sucesso,
                "falhas": total_falhas,
                "pulados": total_pulados
            },
            "detalhes": detalhes,
            "banco": {
                "total_registros": total_registros,
                "top_tickers": top_tickers
            }
        }

    def obter_datas_disponiveis(self) -> List[str]:
        """Retorna datas úteis B3 disponíveis — respeita D+1 e feriados"""

        # Feriados B3 2026
        feriados_b3 = {
            date(2026, 1, 1),
            date(2026, 2, 16),   # Carnaval segunda
            date(2026, 2, 17),   # Carnaval terça
            date(2026, 2, 18),   # Quarta-feira de Cinzas
            date(2026, 4, 3),    # Sexta-feira Santa
            date(2026, 4, 21),   # Tiradentes
            date(2026, 5, 1),    # Dia do Trabalho
            date(2026, 6, 4),    # Corpus Christi
            date(2026, 9, 7),    # Independência
            date(2026, 10, 12),  # N. Sra. Aparecida
            date(2026, 11, 2),   # Finados
            date(2026, 11, 15),  # Proclamação da República
            date(2026, 11, 20),  # Consciência Negra
            date(2026, 12, 24),  # Véspera Natal
            date(2026, 12, 25),  # Natal
            date(2026, 12, 31),  # Véspera Ano Novo
        }

        datas = []
        inicio = date(2026, 2, 9)

        # D+1: dados de ontem só ficam disponíveis hoje
        # último dia seguro = anteontem (hoje - 2)
        fim = date.today() - timedelta(days=2)

        atual = inicio
        while atual <= fim:
            if atual.weekday() < 5 and atual not in feriados_b3:
                datas.append(atual.strftime('%Y%m%d'))
            atual += timedelta(days=1)

        return datas

    def obter_status(self) -> Dict:
        """Retorna status atual do banco"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM opcoes_b3"))
                total = result.fetchone()[0]

                result = conn.execute(text("""
                    SELECT COUNT(DISTINCT data_referencia) 
                    FROM opcoes_b3
                """))
                datas_unicas = result.fetchone()[0]

                result = conn.execute(text("""
                    SELECT MAX(data_referencia) 
                    FROM opcoes_b3
                """))
                ultima_data = result.fetchone()[0]

                result = conn.execute(text("""
                    SELECT ticker, COUNT(*) as total
                    FROM opcoes_b3
                    WHERE ticker IS NOT NULL
                    GROUP BY ticker
                    ORDER BY total DESC
                    LIMIT 10
                """))
                top_tickers = [{"ticker": row[0], "count": row[1]} for row in result]

                return {
                    "total_registros": total,
                    "datas_disponiveis": datas_unicas,
                    "ultima_atualizacao": ultima_data.strftime('%d/%m/%Y') if ultima_data else None,
                    "top_tickers": top_tickers,
                    "status": "conectado"
                }

        except Exception as e:
            self.logger.error(f"❌ Erro ao obter status: {e}")
            return {
                "status": "erro",
                "mensagem": str(e)
            }



# # railway_sync_service.py - Sincroniza dados B3 → Railway

# import requests
# import pandas as pd
# from datetime import datetime
# from sqlalchemy import create_engine, text
# import logging
# from typing import Dict, List, Optional

# class RailwaySyncService:
#     def __init__(self):
#         # Credenciais Railway (hardcoded como você pediu)
#         self.RAILWAY_HOST = "ballast.proxy.rlwy.net"
#         self.RAILWAY_PORT = "33654"
#         self.RAILWAY_USER = "postgres"
#         self.RAILWAY_PASSWORD = "SWYYPTWLukrNVucLgnyImUfTftHSadyS"
#         self.RAILWAY_DATABASE = "railway"
        
#         self.DATABASE_URL = f"postgresql://{self.RAILWAY_USER}:{self.RAILWAY_PASSWORD}@{self.RAILWAY_HOST}:{self.RAILWAY_PORT}/{self.RAILWAY_DATABASE}"
#         self.engine = create_engine(self.DATABASE_URL)
        
#         self.setup_logging()
#         self.garantir_estrutura()
    
#     def setup_logging(self):
#         logging.basicConfig(level=logging.INFO)
#         self.logger = logging.getLogger(__name__)
    
#     def garantir_estrutura(self):
#         """Garante que coluna ticker existe"""
#         try:
#             with self.engine.connect() as conn:
#                 conn.execute(text("""
#                     ALTER TABLE opcoes_b3 
#                     ADD COLUMN IF NOT EXISTS ticker VARCHAR(20)
#                 """))
#                 conn.commit()
#                 self.logger.info(" Estrutura verificada")
#         except Exception as e:
#             self.logger.warning(f" Estrutura: {e}")
    
#     def verificar_data_existe(self, data_obj: datetime) -> bool:
#         """Verifica se data já existe no banco"""
#         try:
#             with self.engine.connect() as conn:
#                 result = conn.execute(text("""
#                     SELECT COUNT(*) as total
#                     FROM opcoes_b3
#                     WHERE data_referencia = :data_ref
#                 """), {"data_ref": data_obj})
                
#                 count = result.fetchone()[0]
#                 return count > 0
#         except Exception as e:
#             self.logger.error(f"❌ Erro ao verificar data: {e}")
#             return False
    
#     def baixar_json_b3(self, data_obj: datetime) -> Optional[Dict]:
#         """Baixa JSON da B3"""
#         folder_date = data_obj.strftime('%Y%m%d')
#         url = f"https://www.b3.com.br/json/{folder_date}/Posicoes/Empresa/SI_C_OPCPOSABEMP.json"
        
#         headers = {
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
#         }
        
#         try:
#             response = requests.get(url, headers=headers, timeout=30)
            
#             if response.status_code == 200:
#                 self.logger.info(f" Download OK: {folder_date}")
#                 return response.json()
#             else:
#                 self.logger.warning(f" HTTP {response.status_code}: {folder_date}")
#                 return None
                
#         except Exception as e:
#             self.logger.error(f"❌ Erro download {folder_date}: {e}")
#             return None
    
#     def processar_json(self, data_json: Dict, data_obj: datetime) -> pd.DataFrame:
#         """Processa JSON em DataFrame"""
#         all_opcoes = []
        
#         for letra, empresas in data_json['Empresa'].items():
#             if empresas:
#                 for opcao in empresas:
#                     opcao['data_referencia'] = data_obj
#                     opcao['tipo_opcao'] = 'CALL' if opcao.get('tMerc') == '70' else 'PUT'
#                     opcao['vencimento'] = pd.to_datetime(opcao['dtVen'], format='%Y%m%d')
                    
#                     mer = opcao.get('mer', '')
#                     esp = opcao.get('espPap', '')
                    
#                     # Gera ticker
#                     if 'ON' in esp:
#                         ticker = f"{mer}3"
#                     elif 'PN' in esp:
#                         ticker = f"{mer}4"
#                     elif 'UNIT' in esp or 'UNT' in esp or 'CI' in esp:
#                         ticker = f"{mer}11"
#                     elif 'DRN' in esp or 'BDR' in esp:
#                         ticker = f"{mer}34"
#                     else:
#                         ticker = mer
                    
#                     opcao['ticker'] = ticker
#                     all_opcoes.append(opcao)
        
#         df = pd.DataFrame(all_opcoes)
        
#         # Renomeia colunas
#         df.rename(columns={
#             'ser': 'serie',
#             'prEx': 'preco_exercicio',
#             'nmEmp': 'empresa',
#             'poCob': 'qtd_coberto',
#             'posDe': 'qtd_descoberto',
#             'posTr': 'qtd_trava',
#             'posTo': 'qtd_total',
#             'qtdClTit': 'clientes_titular',
#             'qtdClLan': 'clientes_lancador',
#             'dtVen': 'vencimento_original',
#             'tMerc': 'tipo_mercado',
#             'mer': 'mercado',
#             'espPap': 'especie_papel'
#         }, inplace=True)
        
#         # Converte tipos
#         df['preco_exercicio'] = pd.to_numeric(df['preco_exercicio'], errors='coerce')
#         df['tipo_opcao'] = df['tipo_opcao'].astype(str)
#         df['qtd_total'] = pd.to_numeric(df['qtd_total'], errors='coerce').fillna(0).astype(int)
#         df['qtd_descoberto'] = pd.to_numeric(df['qtd_descoberto'], errors='coerce').fillna(0).astype(int)
#         df['qtd_trava'] = pd.to_numeric(df['qtd_trava'], errors='coerce').fillna(0).astype(int)
#         df['qtd_coberto'] = pd.to_numeric(df['qtd_coberto'], errors='coerce').fillna(0).astype(int)
        
#         self.logger.info(f" Processados: {len(df)} registros")
#         return df
    
#     def salvar_no_railway(self, df: pd.DataFrame) -> bool:
#         """Salva DataFrame no Railway"""
#         try:
#             df.to_sql('opcoes_b3', self.engine, if_exists='append', index=False)
#             self.logger.info(f"💾 Salvos {len(df)} registros")
#             return True
#         except Exception as e:
#             self.logger.error(f"❌ Erro ao salvar: {e}")
#             return False
    
#     def sincronizar_datas(self, datas: List[str]) -> Dict:
#         """Sincroniza lista de datas"""
#         total_sucesso = 0
#         total_falhas = 0
#         total_pulados = 0
#         detalhes = []
        
#         for i, data_str in enumerate(datas, 1):
#             data_obj = datetime.strptime(data_str, '%Y%m%d')
#             data_formatada = data_obj.strftime('%d/%m/%Y')
            
#             self.logger.info(f"[{i}/{len(datas)}] {data_formatada}")
            
#             # Verifica se já existe
#             if self.verificar_data_existe(data_obj):
#                 self.logger.info(f"⏭️  Já existe, pulando...")
#                 total_pulados += 1
#                 detalhes.append({
#                     "data": data_formatada,
#                     "status": "pulado",
#                     "motivo": "Já existe no banco"
#                 })
#                 continue
            
#             # Baixa JSON
#             json_data = self.baixar_json_b3(data_obj)
            
#             if json_data:
#                 # Processa
#                 df = self.processar_json(json_data, data_obj)
                
#                 # Salva
#                 if self.salvar_no_railway(df):
#                     self.logger.info(f" SUCESSO!")
#                     total_sucesso += 1
#                     detalhes.append({
#                         "data": data_formatada,
#                         "status": "sucesso",
#                         "registros": len(df)
#                     })
#                 else:
#                     total_falhas += 1
#                     detalhes.append({
#                         "data": data_formatada,
#                         "status": "falha",
#                         "motivo": "Erro ao salvar"
#                     })
#             else:
#                 self.logger.warning(f"❌ FALHA - JSON não disponível")
#                 total_falhas += 1
#                 detalhes.append({
#                     "data": data_formatada,
#                     "status": "falha",
#                     "motivo": "JSON não disponível na B3"
#                 })
        
#         # Estatísticas finais
#         with self.engine.connect() as conn:
#             result = conn.execute(text("SELECT COUNT(*) FROM opcoes_b3"))
#             total_registros = result.fetchone()[0]
            
#             # Top 5 tickers
#             result = conn.execute(text("""
#                 SELECT ticker, COUNT(*) as total
#                 FROM opcoes_b3
#                 WHERE ticker IS NOT NULL
#                 GROUP BY ticker
#                 ORDER BY total DESC
#                 LIMIT 5
#             """))
            
#             top_tickers = [{"ticker": row[0], "count": row[1]} for row in result]
        
#         return {
#             "resumo": {
#                 "total_datas": len(datas),
#                 "sucesso": total_sucesso,
#                 "falhas": total_falhas,
#                 "pulados": total_pulados
#             },
#             "detalhes": detalhes,
#             "banco": {
#                 "total_registros": total_registros,
#                 "top_tickers": top_tickers
#             }
#         }
    
#     def obter_datas_disponiveis(self) -> List[str]:
#         """Retorna lista de datas para sincronização"""
#         return [                                   
#             "20260209",
#             "20260210",
#             "20260211",
#             "20260212",
#             "20260213",
#             "20260218",  
#             "20260219",
#             "20260220",
#             "20260223",
#             "20260224",
#             "20260225",
#             "20260226",
#             "20260227",

#         ]

#     #moderni
#     # def obter_datas_disponiveis(self) -> List[str]:
#     #     """Retorna datas úteis B3 disponíveis — respeita D+1"""
#     #     from datetime import date, timedelta
        
#     #     feriados_b3 = {
#     #         date(2026, 1, 1),
#     #         date(2026, 2, 16),  # Carnaval segunda
#     #         date(2026, 2, 17),  # Carnaval terça
#     #         date(2026, 2, 18),  # Quarta de Cinzas
#     #         date(2026, 4, 3),   # Sexta-feira Santa
#     #         date(2026, 4, 21),  # Tiradentes
#     #         date(2026, 5, 1),   # Dia do Trabalho
#     #         date(2026, 6, 4),   # Corpus Christi
#     #         date(2026, 9, 7),   # Independência
#     #         date(2026, 10, 12), # N. Sra. Aparecida
#     #         date(2026, 11, 2),  # Finados
#     #         date(2026, 11, 15), # Proclamação da República
#     #         date(2026, 11, 20), # Consciência Negra
#     #         date(2026, 12, 24), # Véspera Natal
#     #         date(2026, 12, 25), # Natal
#     #         date(2026, 12, 31), # Véspera Ano Novo
#     #     }
        
#     #     datas = []
#     #     inicio = date(2026, 2, 9)
        
#     #     # D+1: dados de ontem só ficam disponíveis hoje
#     #     # então o último dia seguro é anteontem (hoje - 2)
#     #     fim = date.today() - timedelta(days=2)
        
#     #     atual = inicio
#     #     while atual <= fim:
#     #         if atual.weekday() < 5 and atual not in feriados_b3:
#     #             datas.append(atual.strftime('%Y%m%d'))
#     #         atual += timedelta(days=1)
        
#     #     return datas    


#     def obter_status(self) -> Dict:
#         """Retorna status atual do banco"""
#         try:
#             with self.engine.connect() as conn:
#                 # Total de registros
#                 result = conn.execute(text("SELECT COUNT(*) FROM opcoes_b3"))
#                 total = result.fetchone()[0]
                
#                 # Datas únicas
#                 result = conn.execute(text("""
#                     SELECT COUNT(DISTINCT data_referencia) 
#                     FROM opcoes_b3
#                 """))
#                 datas_unicas = result.fetchone()[0]
                
#                 # Última atualização
#                 result = conn.execute(text("""
#                     SELECT MAX(data_referencia) 
#                     FROM opcoes_b3
#                 """))
#                 ultima_data = result.fetchone()[0]
                
#                 # Top tickers
#                 result = conn.execute(text("""
#                     SELECT ticker, COUNT(*) as total
#                     FROM opcoes_b3
#                     WHERE ticker IS NOT NULL
#                     GROUP BY ticker
#                     ORDER BY total DESC
#                     LIMIT 10
#                 """))
                
#                 top_tickers = [{"ticker": row[0], "count": row[1]} for row in result]
                
#                 return {
#                     "total_registros": total,
#                     "datas_disponiveis": datas_unicas,
#                     "ultima_atualizacao": ultima_data.strftime('%d/%m/%Y') if ultima_data else None,
#                     "top_tickers": top_tickers,
#                     "status": "conectado"
#                 }
                
#         except Exception as e:
#             self.logger.error(f"❌ Erro ao obter status: {e}")
#             return {
#                 "status": "erro",
#                 "mensagem": str(e)
#             }