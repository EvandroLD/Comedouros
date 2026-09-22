import motor as mt
from config import *
import time
import RPi.GPIO as GPIO
import balanca as bl
import numpy as np
from utils_config import atualizar_fator_config


_calibracoes = {}


# --- Monitoramento de Botões ---
def monitorar_botao_motor(motor_id, estado_anterior):
    pino_botao = PINO_BOTAO_MANUAL_MOTOR1 if motor_id == 1 else PINO_BOTAO_MANUAL_MOTOR2

    estado_atual = GPIO.input(pino_botao)

    if estado_atual == BOTAO_PRESSIONADO:
        print(f"botão {motor_id} foi pressionado")
        mt._definir_estado_manual(motor_id, 'horario',255)
    elif estado_atual != estado_anterior:
        mt._liberar_controle_manual(motor_id)
    time.sleep(0.05)
    return estado_atual

def setup_botoes():
    GPIO.setup(PINO_BOTAO_MANUAL_MOTOR1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(PINO_BOTAO_MANUAL_MOTOR2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BOTAO_CALIBRAR1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BOTAO_CALIBRAR2, GPIO.IN, pull_up_down=GPIO.PUD_UP)


def calibrar(balanca, estado_anterior):
    pino_botao = BOTAO_CALIBRAR1 if balanca == 1 else BOTAO_CALIBRAR2

    estado_atual = GPIO.input(pino_botao)

    if estado_atual != BOTAO_PRESSIONADO or estado_atual == estado_anterior:
        return estado_atual

    calibracao = _calibracoes.setdefault(
        balanca,
        {"iniciada": False, "leituras": []},
    )

    if not calibracao["iniciada"]:
        calibracao["iniciada"] = True
        calibracao["pesos"] = PESOS_CALIBRACAO_KG[balanca]
        print(
            f"Calibracao da balanca {balanca} comecou; "
            "coloque o primeiro peso e aperte novamente."
        )
        return estado_atual

    numero_ponto = len(calibracao["leituras"])
    leitura = bl.retarar_balanca(balanca)
    calibracao["leituras"].append(float(leitura))

    if numero_ponto < 2:
        mensagens = {
            0: "Coloque o segundo peso e aperte no botao novamente.",
            1: "Coloque o ultimo peso e aperte no botao novamente.",
        }
        print(mensagens[numero_ponto])
        return estado_atual

    pesos = np.asarray(calibracao["pesos"], dtype=float)
    leituras = np.asarray(calibracao["leituras"], dtype=float)
    fator, tara = np.polyfit(pesos, leituras, 1)

    if not np.isfinite(fator) or fator == 0:
        print(f"Falha na calibracao da balanca {balanca}: fator invalido.")
    elif atualizar_fator_config(balanca, fator):
        bl.salvar_tara(balanca, tara)
        BALANCAS[balanca]["fator"] = fator
        print(f"Balanca {balanca} recalibrada; retornando ao ciclo normal.")
    else:
        print(f"Falha ao salvar o fator da balanca {balanca}.")

    _calibracoes.pop(balanca, None)
    return estado_atual



if __name__ == "__main__":
    mt.setup_todos_os_motores()
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(PINO_BOTAO_MANUAL_MOTOR1, GPIO.IN, pull_up_down=GPIO.PUD_UP)



