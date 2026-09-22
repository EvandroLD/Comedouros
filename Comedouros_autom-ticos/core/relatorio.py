# gerenciador relatorio usando google sheets
from datetime import datetime
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import logging
import os
import socket
from config import *
import math

COLUNAS_PESO = {"peso_animal", "peso_racao"}


#Autoriza as credenciais através do json e retorna a primeira aba da planilha
def _autenticar_e_abrir_planilha():
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        LOCAL_CREDENCIAL, SCOPE
    )
    client = gspread.authorize(creds)

    #sheet1 é a primeira aba da tabela
    return client.open(NOME_PLANILHA).sheet1

#APENAS PARA NORMALIZAR DATAS
def normalizar_valor(valor):

    #verificar se é vazio
    if pd.isna(valor):
        return ""

    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M:%S")

    return str(valor).strip()

def normalizar_peso(valor):
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(v):      # pega None, nan e inf
        return ""
    return round(v, 3)          # arredonda (não trunca)


def _normalizar_campo(coluna, valor):
    if coluna in COLUNAS_PESO:
        return normalizar_peso(valor)
    return normalizar_valor(valor)


#RECEBE OS DADOS COMO DICIONARIO, CRIA O CABECALHO E


def salvar_registro_em_sheets(dados_do_registro: dict):
    try:
        planilha = _autenticar_e_abrir_planilha()

        if planilha.row_count == 0:
            cabecalho = list(dados_do_registro.keys())
            planilha.append_row(cabecalho, value_input_option="USER_ENTERED")

        linha_formatada = []
        for chave, valor in dados_do_registro.items():
            linha_formatada.append(_normalizar_campo(chave, valor))

        planilha.append_row(linha_formatada, value_input_option="USER_ENTERED")
        return True

    except Exception as e:
        logging.error(f"Erro ao salvar no Google Sheets: {e}")
        return False


def salvar_registro_csv(csv, dict: dict):
    """
    Salva o dicionário no csv do relatório.
    """
    dados = pd.DataFrame([dict])
    csv = pd.concat([csv, dados], ignore_index=True)
    csv.to_csv(LOCAL_RELATORIO_CSV, index = False)


#COMPARA O CSV LOCAL COM A PLANILHA ONLINE, SE FOR DIFERENTE ENVIA OS DADOS DO LOCAL PARA O ONLINE
def sincronizar_csv_com_sheets():
    try:
        planilha = _autenticar_e_abrir_planilha()

        #APENAS PROCURA SE EXISTE CSV
        if not os.path.exists(LOCAL_RELATORIO_CSV) or os.path.getsize(LOCAL_RELATORIO_CSV) == 0:
            logging.warning("CSV local não encontrado ou vazio. Nada para sincronizar.")
            return 0


        local = pd.read_csv(LOCAL_RELATORIO_CSV)

        if local.empty:
            logging.info("CSV local está vazio. Nenhum dado para sincronizar.")
            return 0

        colunas = list(local.columns)

        online = planilha.get_all_records()

        if online:
            df_sheet = pd.DataFrame(online)
            for coluna in colunas:
                if coluna not in df_sheet.columns:
                    df_sheet[coluna] = ""
            df_sheet = df_sheet[colunas]
        else:
            df_sheet = pd.DataFrame(columns=colunas)

        
        def chave_linha(linha):
            return tuple(_normalizar_campo(coluna, linha[coluna]) for coluna in colunas)

        chaves_sheet = set()
        for _, linha in df_sheet.iterrows():
            chaves_sheet.add(chave_linha(linha))

        registros_faltantes = []

        for _, linha in local.iterrows():
            chave = chave_linha(linha)
            if chave not in chaves_sheet:
                registros_faltantes.append(linha.to_dict())


        if planilha.row_count == 0:
            planilha.append_row(colunas, value_input_option="USER_ENTERED")

        enviados = 0
        for registro in registros_faltantes:
            if salvar_registro_em_sheets(registro):
                enviados += 1
            else:
                logging.error(f"Falha ao sincronizar registro do CSV para Sheets: {registro}")

        logging.info(f"Sincronização concluída: {enviados} registros enviados para o Sheets.")
        return enviados

    except Exception as e:
        logging.error(f"Erro na sincronização CSV x Sheets: {e}")
        return 0

