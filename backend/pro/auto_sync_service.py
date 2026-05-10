# auto_sync_service.py - Verificação e sincronização automática diária do banco B3
# Não altera nenhuma função existente; apenas reutiliza RailwaySyncService.

import threading
from datetime import datetime, timedelta, timezone
from pro.railway_sync_service import RailwaySyncService

# Brasil não adota horário de verão desde 2019 — UTC-3 é sempre correto
_TZ_SP = timezone(timedelta(hours=-3))


class AutoSyncService:
    def __init__(self):
        self._sync_service = None

    def _get_sync_service(self) -> RailwaySyncService:
        if self._sync_service is None:
            self._sync_service = RailwaySyncService()
        return self._sync_service

    def obter_ontem_sp(self):
        """Retorna a data de ontem em UTC-3 (America/Sao_Paulo, sem DST desde 2019)."""
        now_sp = datetime.now(_TZ_SP)
        return (now_sp - timedelta(days=1)).date()

    def obter_ultima_data_banco(self):
        """Retorna a data mais recente no banco, ou None se vazio."""
        datas = self._get_sync_service().listar_datas_no_banco()
        if not datas:
            return None
        # listar_datas_no_banco() retorna ordenado DESC; o primeiro é o mais recente
        return datetime.strptime(datas[0]['data_raw'], '%Y%m%d').date()

    def banco_esta_atualizado(self):
        """Compara a última data do banco com ontem (SP). Retorna (bool, ontem, ultima_data)."""
        ontem = self.obter_ontem_sp()
        ultima_data = self.obter_ultima_data_banco()
        atualizado = ultima_data == ontem if ultima_data is not None else False
        return atualizado, ontem, ultima_data

    def gerar_datas_pendentes(self, ultima_data, ontem):
        """
        Gera dinamicamente todas as datas de (ultima_data + 1 dia) até ontem inclusive.
        Passa todos os dias corridos — a B3 já retorna None para fins de semana/feriados
        e sincronizar_datas() pula datas sem dados disponíveis.
        """
        datas = []
        data_atual = ultima_data + timedelta(days=1)
        while data_atual <= ontem:
            datas.append(data_atual.strftime('%Y%m%d'))
            data_atual += timedelta(days=1)
        return datas

    def executar_verificacao_e_sync(self) -> dict:
        """
        Verifica se o banco está atualizado com base na data de ontem (SP).
        Se não estiver, gera dinamicamente as datas pendentes e dispara a
        sincronização em background via RailwaySyncService — sem alterá-la.
        """
        atualizado, ontem, ultima_data = self.banco_esta_atualizado()

        resultado = {
            "data_referencia_esperada": ontem.strftime('%d/%m/%Y'),
            "ultima_data_banco": ultima_data.strftime('%d/%m/%Y') if ultima_data else None,
            "banco_atualizado": atualizado,
            "sync_disparado": False,
        }

        if not atualizado:
            if ultima_data is None:
                resultado["erro"] = "Banco vazio — execute o sync manual para carregar o histórico inicial."
                return resultado

            datas = self.gerar_datas_pendentes(ultima_data, ontem)

            if not datas:
                resultado["banco_atualizado"] = True
                return resultado

            service = self._get_sync_service()

            def rodar_sync():
                service.sincronizar_datas(datas)

            thread = threading.Thread(target=rodar_sync, daemon=True)
            thread.start()

            resultado["sync_disparado"] = True
            resultado["datas_pendentes"] = datas
            resultado["total_datas_a_sincronizar"] = len(datas)

        return resultado
