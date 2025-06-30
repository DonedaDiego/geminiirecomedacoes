#!/usr/bin/env python3
"""
Diagnóstico Completo - Portfolio System
Verifica conexões, tabelas e funcionalidades críticas
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
import json

class PortfolioDiagnostic:
    def __init__(self):
        self.conn = None
        self.errors = []
        self.warnings = []
        self.info = []
        
    def connect_database(self):
        """Conectar com o banco de dados"""
        try:
            database_url = os.environ.get("DATABASE_URL")
            
            if database_url:
                self.conn = psycopg2.connect(database_url, sslmode='require')
                self.info.append("✅ Conectado via DATABASE_URL (Railway)")
            else:
                self.conn = psycopg2.connect(
                    host=os.environ.get("DB_HOST", "localhost"),
                    database=os.environ.get("DB_NAME", "postgres"),
                    user=os.environ.get("DB_USER", "postgres"),
                    password=os.environ.get("DB_PASSWORD", "#geminii"),
                    port=os.environ.get("DB_PORT", "5432")
                )
                self.info.append("✅ Conectado via variáveis locais")
                
            return True
            
        except Exception as e:
            self.errors.append(f"❌ ERRO DE CONEXÃO: {e}")
            return False
    
    def check_essential_tables(self):
        """Verificar se tabelas essenciais existem"""
        self.info.append("\n🔍 VERIFICANDO TABELAS ESSENCIAIS...")
        
        essential_tables = [
            'users',
            'portfolios', 
            'portfolio_assets',
            'portfolio_recommendations',
            'user_portfolios'
        ]
        
        cursor = self.conn.cursor()
        
        for table in essential_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                self.info.append(f"✅ {table}: {count} registros")
            except Exception as e:
                self.errors.append(f"❌ Tabela {table}: {e}")
        
        cursor.close()
    
    def check_portfolio_structure(self):
        """Verificar estrutura das tabelas de portfolio"""
        self.info.append("\n🏗️ VERIFICANDO ESTRUTURA DAS TABELAS...")
        
        cursor = self.conn.cursor()
        
        # Verificar colunas da portfolio_assets
        try:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'portfolio_assets'
                ORDER BY ordinal_position
            """)
            
            columns = cursor.fetchall()
            self.info.append(f"📋 PORTFOLIO_ASSETS ({len(columns)} colunas):")
            
            expected_columns = ['id', 'portfolio_name', 'ticker', 'weight', 'sector', 
                              'entry_price', 'current_price', 'target_price', 'entry_date']
            
            found_columns = [col[0] for col in columns]
            
            for col in columns:
                self.info.append(f"   - {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'}")
            
            # Verificar se tem todas as colunas necessárias
            missing = set(expected_columns) - set(found_columns)
            if missing:
                self.errors.append(f"❌ Colunas faltando em portfolio_assets: {missing}")
            else:
                self.info.append("✅ Todas as colunas necessárias presentes")
                
        except Exception as e:
            self.errors.append(f"❌ Erro ao verificar portfolio_assets: {e}")
        
        cursor.close()
    
    def test_asset_insertion(self):
        """Testar inserção de ativo (simulação)"""
        self.info.append("\n🧪 TESTANDO INSERÇÃO DE ATIVO...")
        
        cursor = self.conn.cursor()
        
        try:
            # Dados de teste
            test_data = {
                'portfolio_name': 'test_portfolio',
                'ticker': 'TEST4',
                'weight': 25.0,
                'sector': 'Teste',
                'entry_price': 100.00,
                'current_price': 105.00,
                'target_price': 120.00,
                'entry_date': '2024-01-01'
            }
            
            # Tentar inserir (com rollback para não afetar dados reais)
            cursor.execute("BEGIN")
            
            cursor.execute("""
                INSERT INTO portfolio_assets 
                (portfolio_name, ticker, weight, sector, entry_price, current_price, target_price, entry_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                test_data['portfolio_name'],
                test_data['ticker'], 
                test_data['weight'],
                test_data['sector'],
                test_data['entry_price'],
                test_data['current_price'],
                test_data['target_price'],
                test_data['entry_date']
            ))
            
            asset_id = cursor.fetchone()[0]
            self.info.append(f"✅ INSERT simulado bem-sucedido (ID: {asset_id})")
            
            # Rollback para não salvar
            cursor.execute("ROLLBACK")
            self.info.append("✅ Rollback executado - dados não salvos")
            
        except Exception as e:
            cursor.execute("ROLLBACK")
            self.errors.append(f"❌ ERRO no INSERT: {e}")
        
        cursor.close()
    
    def check_admin_permissions(self):
        """Verificar se admin existe e tem permissões"""
        self.info.append("\n👑 VERIFICANDO ADMIN...")
        
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, name, email, user_type, plan_name 
                FROM users 
                WHERE user_type IN ('admin', 'master')
            """)
            
            admins = cursor.fetchall()
            
            if admins:
                self.info.append(f"✅ {len(admins)} admin(s) encontrado(s):")
                for admin in admins:
                    self.info.append(f"   - {admin[1]} ({admin[2]}) - {admin[3]} - {admin[4]}")
            else:
                self.errors.append("❌ Nenhum admin encontrado!")
                
        except Exception as e:
            self.errors.append(f"❌ Erro ao verificar admins: {e}")
        
        cursor.close()
    
    def check_portfolio_data(self):
        """Verificar dados existentes nos portfolios"""
        self.info.append("\n💼 VERIFICANDO DADOS DOS PORTFOLIOS...")
        
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Verificar portfolios disponíveis
            cursor.execute("SELECT name, display_name, is_active FROM portfolios ORDER BY name")
            portfolios = cursor.fetchall()
            
            if portfolios:
                self.info.append(f"📁 {len(portfolios)} carteiras encontradas:")
                for p in portfolios:
                    status = "🟢" if p['is_active'] else "🔴"
                    self.info.append(f"   {status} {p['name']} - {p['display_name']}")
            else:
                self.warnings.append("⚠️ Nenhuma carteira encontrada")
            
            # Verificar ativos por carteira
            cursor.execute("""
                SELECT portfolio_name, COUNT(*) as count, SUM(weight) as total_weight
                FROM portfolio_assets 
                GROUP BY portfolio_name
                ORDER BY portfolio_name
            """)
            
            assets_summary = cursor.fetchall()
            
            if assets_summary:
                self.info.append(f"\n📊 RESUMO DOS ATIVOS:")
                for summary in assets_summary:
                    self.info.append(f"   - {summary['portfolio_name']}: {summary['count']} ativos, {summary['total_weight']:.1f}% peso total")
            else:
                self.warnings.append("⚠️ Nenhum ativo encontrado em nenhuma carteira")
            
            # Verificar recomendações
            cursor.execute("""
                SELECT portfolio_name, action_type, COUNT(*) as count
                FROM portfolio_recommendations 
                WHERE is_active = true
                GROUP BY portfolio_name, action_type
                ORDER BY portfolio_name, action_type
            """)
            
            recs_summary = cursor.fetchall()
            
            if recs_summary:
                self.info.append(f"\n💡 RESUMO DAS RECOMENDAÇÕES:")
                for rec in recs_summary:
                    self.info.append(f"   - {rec['portfolio_name']} {rec['action_type']}: {rec['count']} recomendações")
            else:
                self.warnings.append("⚠️ Nenhuma recomendação ativa encontrada")
                
        except Exception as e:
            self.errors.append(f"❌ Erro ao verificar dados dos portfolios: {e}")
        
        cursor.close()
    
    def test_api_simulation(self):
        """Simular requisição da API"""
        self.info.append("\n🌐 SIMULANDO FLUXO DA API...")
        
        cursor = self.conn.cursor()
        
        try:
            # Simular busca de carteira (como a API faz)
            portfolio_name = 'smart_bdr'
            
            # 1. Verificar se portfolio existe
            cursor.execute("SELECT name, display_name FROM portfolios WHERE name = %s", (portfolio_name,))
            portfolio = cursor.fetchone()
            
            if portfolio:
                self.info.append(f"✅ Portfolio '{portfolio_name}' encontrado: {portfolio[1]}")
            else:
                self.warnings.append(f"⚠️ Portfolio '{portfolio_name}' não encontrado")
            
            # 2. Simular busca de ativos
            cursor.execute("""
                SELECT ticker, weight, sector, entry_price, current_price, target_price 
                FROM portfolio_assets 
                WHERE portfolio_name = %s
                ORDER BY weight DESC
            """, (portfolio_name,))
            
            assets = cursor.fetchall()
            self.info.append(f"📈 {len(assets)} ativos encontrados para {portfolio_name}")
            
            # 3. Simular busca de recomendações  
            cursor.execute("""
                SELECT ticker, action_type, target_weight, recommendation_date
                FROM portfolio_recommendations 
                WHERE portfolio_name = %s AND is_active = true
                ORDER BY recommendation_date DESC
            """, (portfolio_name,))
            
            recommendations = cursor.fetchall()
            self.info.append(f"💡 {len(recommendations)} recomendações ativas para {portfolio_name}")
            
        except Exception as e:
            self.errors.append(f"❌ Erro na simulação API: {e}")
        
        cursor.close()
    
    def run_full_diagnostic(self):
        """Executar diagnóstico completo"""
        print("🔍 INICIANDO DIAGNÓSTICO COMPLETO...")
        print("=" * 60)
        
        # 1. Conectar
        if not self.connect_database():
            self.print_results()
            return False
        
        # 2. Verificações
        self.check_essential_tables()
        self.check_portfolio_structure()  
        self.check_admin_permissions()
        self.check_portfolio_data()
        self.test_asset_insertion()
        self.test_api_simulation()
        
        # 3. Resultados
        self.print_results()
        
        # 4. Fechar conexão
        if self.conn:
            self.conn.close()
            
        return len(self.errors) == 0
    
    def print_results(self):
        """Imprimir resultados do diagnóstico"""
        print("\n" + "=" * 60)
        print("📊 RESULTADOS DO DIAGNÓSTICO")
        print("=" * 60)
        
        # Informações
        if self.info:
            for info in self.info:
                print(info)
        
        # Warnings
        if self.warnings:
            print("\n⚠️ AVISOS:")
            for warning in self.warnings:
                print(warning)
        
        # Erros
        if self.errors:
            print("\n❌ ERROS ENCONTRADOS:")
            for error in self.errors:
                print(error)
        else:
            print("\n🎉 NENHUM ERRO CRÍTICO ENCONTRADO!")
        
        print("\n" + "=" * 60)
        print(f"📈 RESUMO: {len(self.info)} infos, {len(self.warnings)} avisos, {len(self.errors)} erros")
        
        if self.errors:
            print("🔧 AÇÃO NECESSÁRIA: Corrigir os erros listados acima")
        else:
            print("✅ SISTEMA OK: Tabelas e conexões funcionando normalmente")

def create_missing_tables():
    """Criar tabelas que podem estar faltando"""
    print("\n🏗️ CRIANDO/VERIFICANDO TABELAS ESSENCIAIS...")
    
    try:
        # Conectar
        database_url = os.environ.get("DATABASE_URL")
        
        if database_url:
            conn = psycopg2.connect(database_url, sslmode='require')
        else:
            conn = psycopg2.connect(
                host=os.environ.get("DB_HOST", "localhost"),
                database=os.environ.get("DB_NAME", "postgres"),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD", "#geminii"),
                port=os.environ.get("DB_PORT", "5432")
            )
        
        cursor = conn.cursor()
        
        # 1. Tabela portfolios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolios (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                display_name VARCHAR(100) NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✅ Tabela 'portfolios' verificada/criada")
        
        # 2. Inserir portfolios padrão
        portfolios_data = [
            ('smart_bdr', 'Smart BDR', 'Carteira de BDRs inteligentes', True),
            ('growth', 'Growth', 'Carteira de crescimento', True),
            ('smallcaps', 'Small Caps', 'Carteira de pequenas empresas', True),
            ('bluechips', 'Blue Chips', 'Carteira de grandes empresas', True)
        ]
        
        for portfolio in portfolios_data:
            cursor.execute("""
                INSERT INTO portfolios (name, display_name, description, is_active)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name) DO NOTHING
            """, portfolio)
        
        print("✅ Portfolios padrão inseridos")
        
        # 3. Tabela portfolio_assets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_assets (
                id SERIAL PRIMARY KEY,
                portfolio_name VARCHAR(50) NOT NULL,
                ticker VARCHAR(10) NOT NULL,
                weight DECIMAL(5,2) DEFAULT 0,
                sector VARCHAR(100),
                entry_price DECIMAL(10,2),
                current_price DECIMAL(10,2),
                target_price DECIMAL(10,2),
                entry_date DATE,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(portfolio_name, ticker)
            );
        """)
        print("✅ Tabela 'portfolio_assets' verificada/criada")
        
        # 4. Tabela portfolio_recommendations  
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_recommendations (
                id SERIAL PRIMARY KEY,
                portfolio_name VARCHAR(50) NOT NULL,
                ticker VARCHAR(10) NOT NULL,
                action_type VARCHAR(10) NOT NULL CHECK (action_type IN ('BUY', 'SELL', 'HOLD')),
                target_weight DECIMAL(5,2),
                recommendation_date DATE NOT NULL,
                reason TEXT,
                price_target DECIMAL(10,2),
                current_price DECIMAL(10,2),
                entry_price DECIMAL(10,2),
                market_price DECIMAL(10,2),
                is_active BOOLEAN DEFAULT true,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✅ Tabela 'portfolio_recommendations' verificada/criada")
        
        # 5. Tabela user_portfolios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_portfolios (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                portfolio_name VARCHAR(50) NOT NULL,
                is_active BOOLEAN DEFAULT true,
                granted_by INTEGER,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, portfolio_name)
            );
        """)
        print("✅ Tabela 'user_portfolios' verificada/criada")
        
        # 6. Criar índices
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_portfolio_assets_portfolio ON portfolio_assets(portfolio_name)",
            "CREATE INDEX IF NOT EXISTS idx_portfolio_recommendations_portfolio ON portfolio_recommendations(portfolio_name)",
            "CREATE INDEX IF NOT EXISTS idx_user_portfolios_user ON user_portfolios(user_id)"
        ]
        
        for index in indices:
            cursor.execute(index)
        
        print("✅ Índices criados")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("🎉 TODAS AS TABELAS CRIADAS/VERIFICADAS COM SUCESSO!")
        return True
        
    except Exception as e:
        print(f"❌ ERRO ao criar tabelas: {e}")
        return False

if __name__ == "__main__":
    print("🚀 DIAGNÓSTICO DO SISTEMA DE PORTFOLIOS")
    print("🔧 Criado para identificar problemas nas carteiras")
    print()
    
    # Opção de criar tabelas primeiro
    create_tables = input("Deseja criar/verificar tabelas essenciais primeiro? (s/n): ").lower()
    if create_tables == 's':
        create_missing_tables()
        print()
    
    # Executar diagnóstico
    diagnostic = PortfolioDiagnostic()
    success = diagnostic.run_full_diagnostic()
    
    if success:
        print("\n🎯 PRÓXIMOS PASSOS:")
        print("1. Se SQL está executando mas frontend dá erro, verificar:")
        print("   - Se o response JSON está sendo retornado corretamente")
        print("   - Se não há erro de commit/rollback")
        print("   - Se a conexão não está sendo fechada prematuramente")
        print("2. Verificar logs do servidor durante a requisição")
        print("3. Testar rota diretamente no Postman/curl")
    else:
        print("\n🔧 CORRIJA OS ERROS ACIMA ANTES DE CONTINUAR")