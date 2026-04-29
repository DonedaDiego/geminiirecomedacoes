# auto_sync_service.py - Verificação e sincronização automática diária do banco B3
# Não altera nenhuma função existente; apenas reutiliza RailwaySyncService.

import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pro.railway_sync_service import RailwaySyncService

_TIMEZONE_SP = ZoneInfo('America/Sao_Paulo')


class AutoSyncService:
    def __init__(self):
        self._sync_service = None

    def _get_sync_service(self) -> RailwaySyncService:
        if self._sync_service is None:
            self._sync_service = RailwaySyncService()
        return self._sync_service

    def obter_ontem_sp(self):
        """Retorna a data de ontem no timezone America/Sao_Paulo."""
        now_sp = datetime.now(_TIMEZONE_SP)
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

    def executar_verificacao_e_sync(self) -> dict:
        """
        Verifica se o banco está atualizado com base na data de ontem (SP).
        Se não estiver, dispara a sincronização em background usando as
        funções existentes de RailwaySyncService — sem alterá-las.
        """
        atualizado, ontem, ultima_data = self.banco_esta_atualizado()

        resultado = {
            "data_referencia_esperada": ontem.strftime('%d/%m/%Y'),
            "ultima_data_banco": ultima_data.strftime('%d/%m/%Y') if ultima_data else None,
            "banco_atualizado": atualizado,
            "sync_disparado": False,
        }

        if not atualizado:
            service = self._get_sync_service()
            datas = service.obter_datas_disponiveis()

            def rodar_sync():
                service.sincronizar_datas(datas)

            thread = threading.Thread(target=rodar_sync, daemon=True)
            thread.start()

            resultado["sync_disparado"] = True
            resultado["total_datas_verificadas"] = len(datas)

        return resultado
