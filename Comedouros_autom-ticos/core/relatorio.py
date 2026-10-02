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
COLUNAS_DATA = {"hora_entrada", "hora_saida"}

FORMATOS_DATA = (
    "%a %b %d %H:%M:%S %Y",   # formato do CSV
    "%d/%m/%Y %H:%M:%S",      # formato Sheets 
    "%Y-%m-%d %H:%M:%S",
)



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

#tem que alterar ainda
def normalizar_data(valor):
    texto = normalizar_valor(valor)
    for formato in FORMATOS_DATA:
        try:
            return datetime.strptime(texto, formato).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return texto



def normalizar_peso(valor):
    try:
        v = float(str(valor).strip().replace(",", "."))   # aceita "0,301"
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(v):
        return ""
    return round(v, 3)# arredonda 


def _normalizar_campo(coluna, valor):
    if coluna in COLUNAS_PESO:
        return normalizar_peso(valor)
    if coluna in COLUNAS_DATA:
        return normalizar_data(valor)
    return normalizar_valor(valor)




def _planilha_esta_vazia(planilha):
    #row_count é o tamanho da grade (ex: 1000), nunca 0, mesmo com a planilha vazia.
    #por isso é preciso checar as celulas realmente preenchidas.
    return len(planilha.get_all_values()) == 0


def formatar_para_envio(coluna, valor):
    
    if coluna in COLUNAS_PESO:
        return normalizar_peso(valor)
    
    return normalizar_valor(valor)


#GARANTE QUE A PRIMEIRA LINHA DA PLANILHA É O CABECALHO E RETORNA AS LINHAS DE DADOS COMO DICIONARIOS
def _ler_registros_garantindo_cabecalho(planilha, colunas):
    
    valores = planilha.get_all_values(
        value_render_option="UNFORMATTED_VALUE",       # números crus: 0.301, não "0,301"
        date_time_render_option="FORMATTED_STRING",
    )

    if not valores:
        planilha.append_row(colunas, value_input_option="USER_ENTERED")
        return []

    primeira_linha = [str(celula).strip() for celula in valores[0]]

    #se a primeira linha não tem nenhum nome de coluna, ela é um registro e o cabecalho foi perdido.
    #nesse caso o cabecalho é inserido no topo e todas as linhas são tratadas como dados, na ordem do CSV.
    if not set(primeira_linha) & set(colunas):
        logging.warning("Planilha sem cabeçalho na primeira linha. Inserindo o cabeçalho.")
        planilha.insert_row(colunas, index=1, value_input_option="USER_ENTERED")
        cabecalho = colunas
        linhas = valores
    else:
        cabecalho = primeira_linha
        linhas = valores[1:]

    registros = []
    for linha in linhas:
        registro = {}
        for posicao, nome in enumerate(cabecalho):
            if nome and nome not in registro:
                registro[nome] = linha[posicao] if posicao < len(linha) else ""
        registros.append(registro)
    return registros


def salvar_registro_em_sheets(dados_do_registro: dict):
    try:
        planilha = _autenticar_e_abrir_planilha()

        if _planilha_esta_vazia(planilha):
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

        if not os.path.exists(LOCAL_RELATORIO_CSV) or os.path.getsize(LOCAL_RELATORIO_CSV) == 0:
            logging.warning("CSV local não encontrado ou vazio. Nada para sincronizar.")
            return 0

        #dtype=str evita que "11" vire "11.0" quando a coluna tem vazios
        local = pd.read_csv(LOCAL_RELATORIO_CSV, dtype=str, keep_default_na=False)

        if local.empty:
            logging.info("CSV local está vazio. Nenhum dado para sincronizar.")
            return 0

        colunas = list(local.columns)
        online = _ler_registros_garantindo_cabecalho(planilha, colunas)

        def chave(registro):
            return tuple(_normalizar_campo(c, registro.get(c, "")) for c in colunas)

        chaves_sheet = {chave(r) for r in online}

        linhas_novas = []
        for registro in local.to_dict("records"):
            k = chave(registro)
            if k not in chaves_sheet:
                linhas_novas.append([formatar_para_envio(c, registro[c]) for c in colunas])
                chaves_sheet.add(k)

        if linhas_novas:
            #uma única chamada à API; RAW impede o Sheets de converter as datas
            planilha.append_rows(linhas_novas, value_input_option="RAW")

        logging.info(f"Sincronização concluída: {len(linhas_novas)} registros enviados para o Sheets.")
        return len(linhas_novas)

    except Exception as e:
        logging.error(f"Erro na sincronização CSV x Sheets: {e}")
        return 0