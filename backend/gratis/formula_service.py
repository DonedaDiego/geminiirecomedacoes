# formula_service.py - Serviço da Fórmula Mágica Joel Greenblatt

import psycopg2
import pandas as pd
import os
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class FormulaService:
    """Serviço para aplicar a Fórmula Mágica do Joel Greenblatt"""
    
    def __init__(self):
        self.conn_params = self._get_db_connection()
    
    def _get_db_connection(self) -> dict:
        """Obtém parâmetros de conexão do banco de dados"""
        # Detecta se está no Railway ou local baseado na variável FLASK_ENV
        flask_env = os.getenv('FLASK_ENV', 'production')
        
        if flask_env == 'development':
            # Banco local - suas configurações
            return {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', 5432)),
                'dbname': os.getenv('DB_NAME', 'postgres'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', '#geminii')
            }
        else:
            # Railway (produção)
            return {
                'host': os.getenv('DB_HOST', 'ballast.proxy.rlwy.net'),
                'port': int(os.getenv('DB_PORT', 33654)),
                'dbname': os.getenv('DB_NAME', 'railway'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', 'SWYYPTWLukrNVucLgnyImUfTftHSadyS')
            }
    
    def _conectar_banco(self):
        """Conecta ao banco de dados"""
        try:
            return psycopg2.connect(**self.conn_params)
        except Exception as e:
            logger.error(f"Erro na conexão com banco: {e}")
            raise
    
    def _converter_percentual(self, valor) -> Optional[float]:
        """Converte string percentual para float"""
        if not valor or valor == '-' or valor == '':
            return None
        try:
            if isinstance(valor, str):
                # Remove % e converte vírgula para ponto
                valor_limpo = valor.replace('%', '').replace(',', '.').strip()
                if valor_limpo == '':
                    return None
                return float(valor_limpo) / 100 if '%' in valor else float(valor_limpo)
            return float(valor)
        except (ValueError, TypeError):
            return None
    
    def _converter_numero(self, valor) -> Optional[float]:
        """Converte string numérica para float"""
        if not valor or valor == '-' or valor == '':
            return None
        try:
            if isinstance(valor, str):
                # Remove formatação brasileira
                valor_limpo = valor.replace('.', '').replace(',', '.').strip()
                if valor_limpo == '':
                    return None
                return float(valor_limpo)
            return float(valor)
        except (ValueError, TypeError):
            return None
    
    def obter_dados_fundamentalistas(self, 
                                   filtrar_liquidez: bool = True,
                                   liquidez_minima: float = 1000000) -> pd.DataFrame:
        """
        Obtém dados fundamentalistas do banco
        
        Args:
            filtrar_liquidez: Se deve filtrar por liquidez
            liquidez_minima: Valor mínimo de liquidez (padrão: 1M)
        
        Returns:
            DataFrame com os dados
        """
        try:
            conn = self._conectar_banco()
            
            # Query base
            query = """
            SELECT 
                papel,
                cotacao,
                roic,
                ev_ebit,
                mrg_ebit,
                mrg_liq,
                liq_2meses,
                patrim_liq,
                div_yield,
                p_l,
                p_vp,
                p_ebit,
                roe,
                liq_corr
            FROM banco_fundamentalista
            WHERE papel IS NOT NULL 
            AND cotacao IS NOT NULL
            """
            
            # Filtro de liquidez se solicitado
            if filtrar_liquidez:
                query += " AND liq_2meses IS NOT NULL"
            
            query += " ORDER BY papel"
            
            # Executar query
            df = pd.read_sql(query, conn)
            conn.close()
            
            logger.info(f"Dados carregados: {len(df)} empresas")
            return df
            
        except Exception as e:
            logger.error(f"Erro ao obter dados fundamentalistas: {e}")
            raise
    
    def calcular_formula_magica(self, 
                              df: pd.DataFrame,
                              filtrar_negativos: bool = True) -> pd.DataFrame:
        """
        Calcula a Fórmula Mágica do Joel Greenblatt
        
        Args:
            df: DataFrame com dados fundamentalistas
            filtrar_negativos: Se deve filtrar empresas com ROIC ou EV/EBIT negativos
        
        Returns:
            DataFrame com rankings da Fórmula Mágica
        """
        try:
            # Converter campos para numérico
            df_calc = df.copy()
            
            # Conversões
            df_calc['roic_num'] = df_calc['roic'].apply(self._converter_percentual)
            df_calc['ev_ebit_num'] = df_calc['ev_ebit'].apply(self._converter_numero)
            df_calc['cotacao_num'] = df_calc['cotacao'].apply(self._converter_numero)
            df_calc['liq_2meses_num'] = df_calc['liq_2meses'].apply(self._converter_numero)
            
            # Calcular Earnings Yield (inverso do EV/EBIT)
            df_calc['earnings_yield'] = 1 / df_calc['ev_ebit_num'].where(df_calc['ev_ebit_num'] > 0)
            
            # Filtrar dados válidos
            df_valido = df_calc.dropna(subset=['roic_num', 'ev_ebit_num', 'earnings_yield'])
            
            # Filtrar negativos se solicitado
            if filtrar_negativos:
                df_valido = df_valido[
                    (df_valido['roic_num'] > 0) & 
                    (df_valido['ev_ebit_num'] > 0) &
                    (df_valido['earnings_yield'] > 0)
                ]
            
            if df_valido.empty:
                logger.warning("Nenhuma empresa com dados válidos para a Fórmula Mágica")
                return pd.DataFrame()
            
            # Calcular rankings
            df_valido['rank_roic'] = df_valido['roic_num'].rank(ascending=False)
            df_valido['rank_earnings_yield'] = df_valido['earnings_yield'].rank(ascending=False)
            
            # Ranking combinado (menor é melhor)
            df_valido['rank_combinado'] = df_valido['rank_roic'] + df_valido['rank_earnings_yield']
            df_valido['posicao_formula_magica'] = df_valido['rank_combinado'].rank(ascending=True)
            
            # Ordenar pelo ranking combinado
            resultado = df_valido.sort_values('rank_combinado')
            
            # Adicionar campos calculados formatados
            resultado['roic_formatado'] = resultado['roic_num'].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "-")
            resultado['earnings_yield_formatado'] = resultado['earnings_yield'].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "-")
            resultado['ev_ebit_formatado'] = resultado['ev_ebit_num'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "-")
            
            logger.info(f"Fórmula Mágica calculada para {len(resultado)} empresas")
            return resultado
            
        except Exception as e:
            logger.error(f"Erro ao calcular Fórmula Mágica: {e}")
            raise
    
    def obter_top_formula_magica(self, 
                               limite: int = 20,
                               filtrar_liquidez: bool = True,
                               liquidez_minima: float = 1000000) -> List[Dict]:
        """
        Obtém o top ranking da Fórmula Mágica
        
        Args:
            limite: Número de empresas no ranking
            filtrar_liquidez: Se deve filtrar por liquidez
            liquidez_minima: Valor mínimo de liquidez
        
        Returns:
            Lista com o ranking das melhores empresas
        """
        try:
            # Obter dados
            df = self.obter_dados_fundamentalistas(
                filtrar_liquidez=filtrar_liquidez,
                liquidez_minima=liquidez_minima
            )
            
            if df.empty:
                return []
            
            # Calcular Fórmula Mágica
            df_ranking = self.calcular_formula_magica(df)
            
            if df_ranking.empty:
                return []
            
            # Selecionar top empresas
            top_empresas = df_ranking.head(limite)
            
            # Converter para lista de dicionários
            resultado = []
            for _, empresa in top_empresas.iterrows():
                resultado.append({
                    'posicao': int(empresa['posicao_formula_magica']),
                    'papel': empresa['papel'],
                    'cotacao': float(empresa['cotacao_num']) if pd.notna(empresa['cotacao_num']) else None,
                    'roic': empresa['roic_formatado'],
                    'roic_num': float(empresa['roic_num']) if pd.notna(empresa['roic_num']) else None,
                    'earnings_yield': empresa['earnings_yield_formatado'],
                    'earnings_yield_num': float(empresa['earnings_yield']) if pd.notna(empresa['earnings_yield']) else None,
                    'ev_ebit': empresa['ev_ebit_formatado'],
                    'ev_ebit_num': float(empresa['ev_ebit_num']) if pd.notna(empresa['ev_ebit_num']) else None,
                    'rank_roic': int(empresa['rank_roic']),
                    'rank_earnings_yield': int(empresa['rank_earnings_yield']),
                    'rank_combinado': float(empresa['rank_combinado']),
                    'liquidez_2m': empresa['liq_2meses'],
                    'div_yield': empresa['div_yield'],
                    'p_l': empresa['p_l'],
                    'margem_ebit': empresa['mrg_ebit'],
                    'margem_liquida': empresa['mrg_liq']
                })
            
            logger.info(f"Top {len(resultado)} empresas da Fórmula Mágica gerado")
            return resultado
            
        except Exception as e:
            logger.error(f"Erro ao obter top Fórmula Mágica: {e}")
            raise
    
    def obter_estatisticas_base(self) -> Dict:
        """
        Obtém estatísticas da base de dados
        
        Returns:
            Dicionário com estatísticas
        """
        try:
            conn = self._conectar_banco()
            cursor = conn.cursor()
            
            # Total de empresas
            cursor.execute("SELECT COUNT(*) FROM banco_fundamentalista")
            total_empresas = cursor.fetchone()[0]
            
            # Empresas com ROIC válido
            cursor.execute("""
                SELECT COUNT(*) FROM banco_fundamentalista 
                WHERE roic IS NOT NULL AND roic != '-'
            """)
            empresas_roic = cursor.fetchone()[0]
            
            # Empresas com EV/EBIT válido
            cursor.execute("""
                SELECT COUNT(*) FROM banco_fundamentalista 
                WHERE ev_ebit IS NOT NULL
            """)
            empresas_ev_ebit = cursor.fetchone()[0]
            
            # Empresas com liquidez
            cursor.execute("""
                SELECT COUNT(*) FROM banco_fundamentalista 
                WHERE liq_2meses IS NOT NULL
            """)
            empresas_liquidez = cursor.fetchone()[0]
            
            # Data da última atualização
            cursor.execute("SELECT MAX(data_importacao) FROM banco_fundamentalista")
            ultima_atualizacao = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_empresas': total_empresas,
                'empresas_roic_valido': empresas_roic,
                'empresas_ev_ebit_valido': empresas_ev_ebit,
                'empresas_liquidez_valida': empresas_liquidez,
                'ultima_atualizacao': ultima_atualizacao.isoformat() if ultima_atualizacao else None,
                'percentual_dados_completos': round((min(empresas_roic, empresas_ev_ebit) / total_empresas * 100), 2) if total_empresas > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            raise
    
    def buscar_empresa(self, papel: str) -> Optional[Dict]:
        """
        Busca dados de uma empresa específica
        
        Args:
            papel: Código da empresa (ex: PETR4)
        
        Returns:
            Dicionário com dados da empresa ou None se não encontrada
        """
        try:
            conn = self._conectar_banco()
            
            query = """
            SELECT * FROM banco_fundamentalista 
            WHERE UPPER(papel) = UPPER(%s)
            LIMIT 1
            """
            
            df = pd.read_sql(query, conn, params=[papel])
            conn.close()
            
            if df.empty:
                return None
            
            empresa = df.iloc[0].to_dict()
            
            # Converter campos numéricos
            empresa['roic_num'] = self._converter_percentual(empresa['roic'])
            empresa['ev_ebit_num'] = self._converter_numero(empresa['ev_ebit'])
            empresa['cotacao_num'] = self._converter_numero(empresa['cotacao'])
            
            # Calcular earnings yield
            if empresa['ev_ebit_num'] and empresa['ev_ebit_num'] > 0:
                empresa['earnings_yield'] = 1 / empresa['ev_ebit_num']
                empresa['earnings_yield_formatado'] = f"{empresa['earnings_yield']*100:.2f}%"
            else:
                empresa['earnings_yield'] = None
                empresa['earnings_yield_formatado'] = "-"
            
            return empresa
            
        except Exception as e:
            logger.error(f"Erro ao buscar empresa {papel}: {e}")
            raise


# Instância global do serviço
formula_service = FormulaService()