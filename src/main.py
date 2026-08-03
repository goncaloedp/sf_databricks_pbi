import os
import json
import hashlib
import datetime
import traceback
import pandas
from salesforce import (
    ligacao_salesforce,
    ids_ativos,
    obter_ativos,
    obter_eventos,
    obter_po,
    construir_task_owner,
    obter_sintoma_eventos_pai,
    obter_empresa,
    obter_ct_eq_tomadas
)


PATH_CURRENT = r"C:\Users\E713362\OneDrive - EDP\O365_CSI_ME_Dashboards - Current"
PATH_LOGS = r"C:\Users\E713362\OneDrive - EDP\O365_CSI_ME_Dashboards - Logs"
STATE_PATH = os.path.join(PATH_LOGS, "state.json")
FORCE_FULL_REFRESH = True


def utc_now_iso():
    # Data atual para controlar o incremental
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalizar_timestamp_salesforce(valor):
    # Garante o formato válido para filtros SOQL com LastModifiedDate
    if valor is None:
        return None

    data = pandas.to_datetime(valor, utc=True, errors="coerce")

    if pandas.isna(data):
        return None

    return data.strftime("%Y-%m-%dT%H:%M:%SZ")


def ler_state():
    # Lê a última execução bem-sucedida
    if not os.path.exists(STATE_PATH):
        return {}

    with open(STATE_PATH, "r", encoding="utf-8") as ficheiro:
        return json.load(ficheiro)


def guardar_state(state):
    # Guarda o state da execução atual
    os.makedirs(PATH_LOGS, exist_ok=True)

    with open(STATE_PATH, "w", encoding="utf-8") as ficheiro:
        json.dump(state, ficheiro, indent=4, ensure_ascii=False)


def ler_csv_atual(nome):
    # Lê o CSV existente para fazer upsert
    caminho = os.path.join(PATH_CURRENT, f"{nome}.csv")

    if not os.path.exists(caminho):
        return pandas.DataFrame()

    return pandas.read_csv(caminho, sep=";", encoding="utf-8-sig", dtype="string")


def upsert_por_chave(df_atual, df_delta, chave):
    # Mantém a tabela atual se não houver delta
    if df_delta is None or df_delta.empty:
        return df_atual

    # Se não existir tabela atual, devolve o delta
    if df_atual is None or df_atual.empty:
        return df_delta

    # Evita substituir a tabela completa por engano
    if chave not in df_atual.columns:
        raise ValueError(f"Chave '{chave}' não existe no CSV atual.")

    if chave not in df_delta.columns:
        raise ValueError(f"Chave '{chave}' não existe no delta.")

    df_atual = df_atual.copy()
    df_delta = df_delta.copy()
    df_atual[chave] = df_atual[chave].astype("string")
    df_delta[chave] = df_delta[chave].astype("string")
    df_atual = df_atual[~df_atual[chave].isin(df_delta[chave])]

    return pandas.concat([df_atual, df_delta], ignore_index=True)


def exportar_csv(df, nome, ordenar_por=None):
    # Exporta apenas se o conteúdo tiver alterado
    os.makedirs(PATH_CURRENT, exist_ok=True)
    os.makedirs(PATH_LOGS, exist_ok=True)

    if df is None:
        df = pandas.DataFrame()

    df = df.copy()

    # Ordena para evitar alterações falsas no hash
    if ordenar_por is not None:
        colunas_ordenacao = [coluna for coluna in ordenar_por if coluna in df.columns]

        if colunas_ordenacao:
            df = df.sort_values(by=colunas_ordenacao).reset_index(drop=True)

    csv_texto = df.to_csv(index=False, sep=";", lineterminator="\n")

    # utf-8-sig evita problemas com acentos
    csv_bytes = csv_texto.encode("utf-8-sig")
    hash_novo = hashlib.sha256(csv_bytes).hexdigest()

    caminho_csv = os.path.join(PATH_CURRENT, f"{nome}.csv")
    caminho_hash = os.path.join(PATH_LOGS, f"{nome}.sha256")
    caminho_temp = os.path.join(PATH_CURRENT, f"{nome}.tmp")

    if os.path.exists(caminho_hash):
        with open(caminho_hash, "r", encoding="utf-8") as ficheiro_hash:
            hash_atual = ficheiro_hash.read().strip()
    else:
        hash_atual = None

    if hash_atual == hash_novo:
        print(f"{nome}.csv já está atualizado.")
        return False

    with open(caminho_temp, "wb") as ficheiro_temp:
        ficheiro_temp.write(csv_bytes)

    try:
        os.replace(caminho_temp, caminho_csv)
    except PermissionError:
        if os.path.exists(caminho_temp):
            os.remove(caminho_temp)

        raise PermissionError(f"Não foi possível atualizar {nome}.csv. "f"Fecha o ficheiro no Excel/Power BI e confirma que o OneDrive não está a bloquear o ficheiro.")

    with open(caminho_hash, "w", encoding="utf-8") as ficheiro_hash:
        ficheiro_hash.write(hash_novo)

    print(f"{nome}.csv exportado.")
    return True


def exportar_tabela(df, nome, ordenar_por=None):
    # Converte True/False em 1/0 para contar ficheiros atualizados
    return int(exportar_csv(df, nome, ordenar_por=ordenar_por))


def main():
    print("Conectando ao Salesforce...")

    try:
        sf = ligacao_salesforce()

        if sf is None:
            print("Erro na ligação.")
            return

        print("Ligação estabelecida com sucesso.")

        lista_ids = ids_ativos(sf)

        if not lista_ids:
            print("Sem ativos.")
            return

        print(f"Número de ativos: {len(lista_ids)}")

        # Período de análise
        periodo = [datetime.date.today() - datetime.timedelta(days=3000),datetime.date.today()]

        # Ler estado incremental
        state = ler_state()
        desde = normalizar_timestamp_salesforce(state.get("last_success_utc"))

        ficheiros_incrementais = ["eventos.csv", "pedidos_operacao.csv"]

        # Força full refresh se definido ou se algum dos CSVs incrementais não existir
        if (FORCE_FULL_REFRESH or any(not os.path.exists(os.path.join(PATH_CURRENT, f)) for f in ficheiros_incrementais)):
            desde = None

        run_timestamp_utc = utc_now_iso()
        ficheiros_atualizados = 0

        # Ativos
        ativos = obter_ativos(
            sf_=sf,
            lista=lista_ids
        )

        ficheiros_atualizados += exportar_tabela(
            ativos,
            "ativos",
            ordenar_por=["salesforce_id"]
        )
        
        # Eventos
        eventos_delta = obter_eventos(
            sf_=sf,
            lista=lista_ids,
            periodo=periodo,
            meio=[],
            estado=[],
            desde=desde
        )

        if desde is not None:
            eventos_atual = ler_csv_atual("eventos")
            eventos = upsert_por_chave(
                eventos_atual,
                eventos_delta,
                "case_id"
            )
        else:
            eventos = eventos_delta

        # Pedidos de Operação
        pedidos_operacao_delta = obter_po(
            sf_=sf,
            lista=lista_ids,
            meio=[],
            estado=[],
            desde=desde
        )

        if desde is not None:
            pedidos_operacao_atual = ler_csv_atual("pedidos_operacao")

            pedidos_operacao = upsert_por_chave(
                pedidos_operacao_atual,
                pedidos_operacao_delta,
                "case_id"
            )
        else:
            pedidos_operacao = pedidos_operacao_delta

        # Export Eventos + POs
        eventos = construir_task_owner(
            eventos,
            pedidos_operacao
        )

        ficheiros_atualizados += exportar_tabela(
            eventos,
            "eventos",
            ordenar_por=["case_id"]
        )

        ficheiros_atualizados += exportar_tabela(
            pedidos_operacao,
            "pedidos_operacao",
            ordenar_por=["case_id"]
        )

        # Empresa/Cliente
        empresa = obter_empresa(
            sf_=sf,
            lista=lista_ids
        )

        ficheiros_atualizados += exportar_tabela(
            empresa,
            "empresa",
            ordenar_por=["salesforce_id", "empresa_id"]
        )

        # Controlo Técnico + Equipamentos + Tomadas
        ct, eq, tomadas = obter_ct_eq_tomadas(
            sf_=sf,
            lista=lista_ids
        )

        # Controlo Técnico
        ficheiros_atualizados += exportar_tabela(
            ct,
            "ct_me",
            ordenar_por=["salesforce_id", "ct_id"]
        )

        # Equipamentos
        ficheiros_atualizados += exportar_tabela(
            eq,
            "equipamentos_me",
            ordenar_por=["salesforce_id", "ct_id", "eq_id"]
        )

        # Tomadas
        ficheiros_atualizados += exportar_tabela(
            tomadas,
            "tomadas_me",
            ordenar_por=["salesforce_id", "ct_id", "eq_id", "componente_eq_id"]
        )

        # Sintomas dos eventos pai
        if eventos is not None and not eventos.empty and "case_id" in eventos.columns:
            lista_cases = eventos["case_id"].dropna().astype(str).unique().tolist()
        elif eventos is not None and not eventos.empty and "Id" in eventos.columns:
            lista_cases = eventos["Id"].dropna().astype(str).unique().tolist()
        else:
            lista_cases = []

        if lista_cases:
            sintomas_eventos_pai = obter_sintoma_eventos_pai(
                sf_=sf,
                lista_solicitacoes=lista_cases
            )
        else:
            sintomas_eventos_pai = pandas.DataFrame()

        ficheiros_atualizados += exportar_tabela(
            sintomas_eventos_pai,
            "sintomas_eventos_pai",
            ordenar_por=["case_id"]
        )

        # Atualiza o state só no fim da execução bem-sucedida
        state["last_success_utc"] = run_timestamp_utc
        state["last_success_local"] = datetime.datetime.now().isoformat()
        state["ficheiros_atualizados_ultima_execucao"] = ficheiros_atualizados
        guardar_state(state)

        if ficheiros_atualizados == 0:
            print("Não foi necessário exportar tabelas para o SharePoint. Todos os CSVs já estavam atualizados.")
        else:
            print(f"Exportação concluída. Ficheiros atualizados: {ficheiros_atualizados}")

    except Exception as e:
        print("Erro durante execução:")
        print(e)
        traceback.print_exc()


if __name__ == "__main__":
    main()