import os
import duckdb
from flask import Blueprint, jsonify, request

DATA_DIR = r"C:\Users\Diego\Desktop\VSCode\dadoscvm" if os.name == "nt" else "/data"


def _con(banco):
    return duckdb.connect(f"{DATA_DIR}/{banco}.duckdb", read_only=True)


def _resolve_cnpj(ticker):
    con_t = _con("dados_tickers")
    row = con_t.execute(
        "SELECT cnpj FROM tickers WHERE ticker = ? LIMIT 1", [ticker]
    ).fetchone()
    con_t.close()
    return row[0] if row else None


def get_fundamentos_blueprint():
    bp = Blueprint("fundamentos", __name__)

    @bp.route("/api/info")
    def info():
        ticker = request.args.get("ticker", "").upper().strip()
        cnpj   = request.args.get("cnpj", "").strip()
        if not ticker and not cnpj:
            return jsonify({"empresa": "", "cnpj": "", "segmento": ""})
        try:
            con = _con("dados_tickers")
            if cnpj:
                row = con.execute(
                    "SELECT nome_empresa, cnpj, segmento FROM tickers WHERE cnpj = ? LIMIT 1", [cnpj]
                ).fetchone()
            else:
                row = con.execute(
                    "SELECT nome_empresa, cnpj, segmento FROM tickers WHERE ticker = ? LIMIT 1", [ticker]
                ).fetchone()
            con.close()
            if row:
                return jsonify({"empresa": row[0], "cnpj": row[1], "segmento": row[2] or ""})
            return jsonify({"empresa": ticker, "cnpj": cnpj, "segmento": ""})
        except Exception as e:
            return jsonify({"empresa": ticker, "cnpj": cnpj, "segmento": "", "erro": str(e)})

    @bp.route("/api/balanco")
    def balanco():
        ticker = request.args.get("ticker", "").upper().strip()
        cnpj   = request.args.get("cnpj", "").strip()
        if not ticker and not cnpj:
            return jsonify([])

        CONTAS = (
            "1", "1.01", "1.01.01", "1.01.02", "1.01.03", "1.01.04",
            "1.01.06", "1.01.08",
            "1.02", "1.02.01", "1.02.02", "1.02.03", "1.02.04",
            "2", "2.01", "2.01.02", "2.01.04",
            "2.02", "2.02.01", "2.03",
        )
        placeholders = ", ".join(["?" for _ in CONTAS])

        try:
            if not cnpj and ticker:
                cnpj = _resolve_cnpj(ticker)
            if not cnpj:
                return jsonify([])

            con = _con("dados_dfp")
            rows = con.execute(
                f"""
                SELECT cd_conta, ano, vl_conta
                FROM dados_dfp
                WHERE cnpj_cia = ?
                  AND cd_conta IN ({placeholders})
                  AND con_ind = 'DF Consolidado'
                  AND tipo_dem IN ('Balanço Patrimonial Ativo', 'Balanço Patrimonial Passivo')
                  AND ordem_exerc = 'ÚLTIMO'
                ORDER BY ano ASC, cd_conta ASC
                """,
                [cnpj, *CONTAS]
            ).fetchall()
            con.close()

            return jsonify([{"cd_conta": r[0], "ano": r[1], "vl_conta": r[2]} for r in rows])

        except Exception as e:
            return jsonify({"erro": str(e)}), 500

    @bp.route("/api/dre")
    def dre():
        ticker = request.args.get("ticker", "").upper().strip()
        cnpj   = request.args.get("cnpj", "").strip()
        if not ticker and not cnpj:
            return jsonify([])

        CONTAS = (
            "3.01", "3.02", "3.04", "3.05",
            "3.06.01", "3.06.02", "3.07", "3.08",
            "3.09", "3.10", "3.11",
            "6.01.01.04", "6.02.01",
        )
        placeholders = ", ".join(["?" for _ in CONTAS])

        try:
            if not cnpj and ticker:
                cnpj = _resolve_cnpj(ticker)
            if not cnpj:
                return jsonify([])

            con = _con("dados_dfp")
            rows = con.execute(
                f"""
                SELECT cd_conta, ano, vl_conta
                FROM dados_dfp
                WHERE cnpj_cia = ?
                  AND cd_conta IN ({placeholders})
                  AND con_ind = 'DF Consolidado'
                  AND tipo_dem = 'Demonstração do Resultado'
                  AND ordem_exerc = 'ÚLTIMO'
                ORDER BY ano ASC, cd_conta ASC
                """,
                [cnpj, *CONTAS]
            ).fetchall()
            con.close()

            return jsonify([{"cd_conta": r[0], "ano": r[1], "vl_conta": r[2]} for r in rows])

        except Exception as e:
            return jsonify({"erro": str(e)}), 500

    @bp.route("/api/tickers/busca")
    def busca_tickers():
        q = request.args.get("q", "").upper().strip()
        if not q or len(q) < 2:
            return jsonify([])
        try:
            con = _con("dados_tickers")
            rows = con.execute(
                """
                SELECT ticker, nome_pregao, cnpj
                FROM tickers
                WHERE (ticker LIKE ? OR nome_pregao LIKE ?)
                  AND status = 'Ativo'
                ORDER BY ticker ASC
                LIMIT 15
                """,
                [f"{q}%", f"%{q}%"]
            ).fetchall()
            con.close()
            return jsonify([{"ticker": r[0], "nome": r[1], "cnpj": r[2]} for r in rows])
        except Exception as e:
            return jsonify({"erro": str(e)}), 500

    return bp