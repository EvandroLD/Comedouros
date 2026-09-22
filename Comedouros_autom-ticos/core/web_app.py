import csv
import logging
import os
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException
import RPi.GPIO as GPIO

import balanca as bl
import motor
from config import BALANCAS, TAG_INFO_CSV

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


@app.errorhandler(Exception)
def tratar_erro_como_json(erro):
    #Sem isso, qualquer excecao (ex: pigpio desconectado) vira uma pagina HTML de
    #erro do Flask; o front-end faz `await r.json()` nela, a promise quebra sem
    #aviso nenhum, e o botao parece simplesmente "nao funcionar".
    if isinstance(erro, HTTPException):
        return erro
    logging.exception("Erro nao tratado em uma rota da API")
    return jsonify(ok=False, erro=str(erro)), 500


HARDWARE_LOCK = threading.RLock()
STATUS_LOCK = threading.Lock()
STATUS = {
    "mensagem": "Aguardando inicializacao",
    "peso1": None,
    "peso2": None,
    "motor1": "parado",
    "motor2": "parado",
}

LOGS = deque(maxlen=100)
CALIBRACAO_B2_PENDENTE = False


def registrar_status(mensagem):
    with STATUS_LOCK:
        STATUS["mensagem"] = mensagem
        LOGS.appendleft(f"{time.strftime('%H:%M:%S')} - {mensagem}")
    logging.info(mensagem)


def caminho_tag_info():
    configurado = Path(TAG_INFO_CSV)
    if configurado.parent.exists():
        return configurado
    return Path(__file__).resolve().parent / "tag_info.csv"


def atualizar_pesos():
    try:
        with HARDWARE_LOCK:
            peso1, _ = bl.ler_peso(1)
            peso2, _ = bl.ler_peso(2)
        with STATUS_LOCK:
            STATUS["peso1"] = peso1
            STATUS["peso2"] = peso2
    except Exception as erro:
        registrar_status(f"Erro ao ler balancas: {erro}")

def estado_motor(numero):
    direcao, velocidade = motor._obter_estado_ativo(numero)
    return "parado" if velocidade <= 0 else f"{direcao} ({velocidade})"


def status_atual():
    atualizar_pesos()
    with STATUS_LOCK:
        resultado = dict(STATUS)
        resultado["motor1"] = estado_motor(1)
        resultado["motor2"] = estado_motor(2)
        resultado["logs"] = list(LOGS)
        return resultado


def calibrar_balanca_1():
    try:
        with HARDWARE_LOCK:
            bl.calibrar_balanca(1)
        registrar_status("Balanca 1 calibrada")
    except Exception as erro:
        registrar_status(f"Erro ao calibrar balanca 1: {erro}")


def iniciar_calibracao_2():
    global CALIBRACAO_B2_PENDENTE
    try:
        with HARDWARE_LOCK:
            bl.calibrar_balanca(2)
        CALIBRACAO_B2_PENDENTE = True
        registrar_status("Balanca 2 zerada. Coloque o peso conhecido e clique em concluir")
    except Exception as erro:
        registrar_status(f"Erro ao zerar balanca 2: {erro}")


@app.get("/api/status")
def api_status():
    return jsonify(status_atual())


@app.post("/api/calibrar/1")
def api_calibrar_1():
    threading.Thread(target=calibrar_balanca_1, daemon=True).start()
    registrar_status("Calibracao da balanca 1 iniciada: retire todo o peso")
    return jsonify(ok=True)


@app.post("/api/calibrar/2")
def api_calibrar_2():
    global CALIBRACAO_B2_PENDENTE
    dados = request.get_json(silent=True) or {}
    peso_conhecido = float(dados.get("peso", 0))
    if peso_conhecido <= 0:
        return jsonify(ok=False, erro="Informe um peso conhecido maior que zero"), 400

    if not CALIBRACAO_B2_PENDENTE:
        threading.Thread(target=iniciar_calibracao_2, daemon=True).start()
        return jsonify(ok=True, etapa="tara", mensagem="Retire o peso. Depois coloque o peso conhecido e clique novamente")

    try:
        with HARDWARE_LOCK:
            leitura, _ = bl.ler_peso(2)
            leitura_bruta = bl.read_count(BALANCAS[2]["DT"], BALANCAS[2]["SCK"])
            tara = BALANCAS[2]["tara"]
            fator = (leitura_bruta - tara) / peso_conhecido
            if fator == 0:
                raise ValueError("fator calculado igual a zero")
            BALANCAS[2]["fator"] = fator
        CALIBRACAO_B2_PENDENTE = False
        registrar_status(f"Balanca 2 calibrada. Fator: {fator:.3f}")
        return jsonify(ok=True, leitura=leitura, fator=fator)
    except Exception as erro:
        registrar_status(f"Erro ao concluir calibracao da balanca 2: {erro}")
        return jsonify(ok=False, erro=str(erro)), 500


@app.post("/api/motor/<int:numero>")
def api_motor(numero):
    if numero not in (1, 2):
        return jsonify(ok=False, erro="Motor invalido"), 400
    dados = request.get_json(silent=True) or {}
    direcao = dados.get("direcao", "horario")
    velocidade = int(dados.get("velocidade", 150))
    try:
        with HARDWARE_LOCK:
            motor._definir_estado_manual(numero, direcao, velocidade)
    except Exception as erro:
        registrar_status(f"Erro ao ligar motor {numero}: {erro}")
        return jsonify(ok=False, erro=str(erro)), 500
    registrar_status(f"Motor {numero} ligado ({direcao}, {velocidade})")
    return jsonify(ok=True)


@app.post("/api/motor/<int:numero>/parar")
def api_parar_motor(numero):
    if numero not in (1, 2):
        return jsonify(ok=False, erro="Motor invalido"), 400
    try:
        with HARDWARE_LOCK:
            motor._definir_estado_manual(numero, "parado", 0)
            motor._liberar_controle_manual(numero)
    except Exception as erro:
        registrar_status(f"Erro ao parar motor {numero}: {erro}")
        return jsonify(ok=False, erro=str(erro)), 500
    registrar_status(f"Motor {numero} parado")
    return jsonify(ok=True)


@app.post("/api/ovelha")
def api_ovelha():
    dados = request.get_json(silent=True) or {}
    obrigatorios = ("tag_id", "nome", "peso")
    if any(not str(dados.get(campo, "")).strip() for campo in obrigatorios):
        return jsonify(ok=False, erro="Informe tag, nome e peso"), 400

    try:
        caminho = caminho_tag_info()
        with HARDWARE_LOCK:
            with caminho.open("r", encoding="utf-8", newline="") as arquivo:
                registros = list(csv.DictReader(arquivo))
                campos = ["tag_id", "tipo", "valor", "nome", "peso", "mestra"]
            tag_id = str(dados["tag_id"]).strip().upper()
            if any(registro.get("tag_id", "").strip().upper() == tag_id for registro in registros):
                return jsonify(ok=False, erro="Essa tag ja esta cadastrada"), 409
            peso = float(dados["peso"])
            registros.append({
                "tag_id": tag_id,
                "tipo": "percentual",
                "valor": peso * 0.2,
                "nome": str(dados["nome"]).strip(),
                "peso": peso,
                "mestra": "False",
            })
            with caminho.open("w", encoding="utf-8", newline="") as arquivo:
                escritor = csv.DictWriter(arquivo, fieldnames=campos)
                escritor.writeheader()
                escritor.writerows(registros)
    except Exception as erro:
        registrar_status(f"Erro ao cadastrar ovelha: {erro}")
        return jsonify(ok=False, erro=str(erro)), 500
    registrar_status(f"Ovelha cadastrada: {dados['nome']}")
    return jsonify(ok=True)


@app.post("/api/reiniciar")
def api_reiniciar():
    try:
        subprocess.Popen(["sudo", "reboot", "0"])
    except Exception as erro:
        registrar_status(f"Erro ao solicitar reinicio: {erro}")
        return jsonify(ok=False, erro=str(erro)), 500
    registrar_status("Reinicio solicitado")
    return jsonify(ok=True)


@app.get("/")
def pagina():
    return render_template("index.html")


if __name__ == "__main__":
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        for numero, configuracao in BALANCAS.items():
            bl.setup_balanca(configuracao["DT"], configuracao["SCK"])
        motor.setup_todos_os_motores()
        registrar_status("Interface pronta")
    except Exception as erro:
        registrar_status(f"Hardware ainda nao inicializado: {erro}")

    app.run(host="0.0.0.0", port=5000)
