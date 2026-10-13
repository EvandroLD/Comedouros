import motor as mt
from config import *
import time
import RPi.GPIO as GPIO
import balanca as bl
import numpy as np
from utils_config import atualizar_fator_config

# O site é opcional: se o web_app não puder ser importado (ex: sem Flask),
# os botões continuam funcionando e só imprimem no terminal.
try:
    import web_app as web
except Exception:
    web = None


_calibracoes = {}
_inicio_aperto = {}             # balanca -> momento (monotonic) em que o botao foi apertado
_cancelada_neste_aperto = set() # balancas cuja calibracao ja foi cancelada no aperto atual


def _avisar(mensagem):
    """Mostra a mensagem no terminal e na área de logs do site."""
    print(mensagem)
    if web is not None:
        try:
            web.registrar_evento_botao(mensagem)
        except Exception as erro:
            print(f"Não foi possível registrar o evento no site: {erro}")


# --- Monitoramento de Botões ---
def monitorar_botao_motor(motor_id, estado_anterior):
    pino_botao = PINO_BOTAO_MANUAL_MOTOR1 if motor_id == 1 else PINO_BOTAO_MANUAL_MOTOR2

    estado_atual = GPIO.input(pino_botao)

    if estado_atual == BOTAO_PRESSIONADO:
        # Só registra na borda (quando acabou de apertar), para não lotar o log a cada 50 ms
        if estado_anterior != BOTAO_PRESSIONADO:
            _avisar(f"Botão do motor {motor_id} pressionado: motor {motor_id} girando (manual)")
        mt._definir_estado_manual(motor_id, 'horario', 255)
    elif estado_atual != estado_anterior:
        mt._liberar_controle_manual(motor_id)
        _avisar(f"Botão do motor {motor_id} solto: controle manual do motor {motor_id} liberado")
    time.sleep(0.05)
    return estado_atual


def setup_botoes():
    GPIO.setup(PINO_BOTAO_MANUAL_MOTOR1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(PINO_BOTAO_MANUAL_MOTOR2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BOTAO_CALIBRAR1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BOTAO_CALIBRAR2, GPIO.IN, pull_up_down=GPIO.PUD_UP)


def calibrar(balanca, estado_anterior):
    """Botao de calibracao:
    - aperto curto (solto antes de TEMPO_CANCELAR_CALIBRACAO): inicia a calibracao ou
      registra o proximo peso. A acao acontece ao SOLTAR o botao, para nao registrar um
      ponto quando a intencao e segurar para cancelar.
    - segurar por TEMPO_CANCELAR_CALIBRACAO com uma calibracao em andamento: cancela,
      descartando os pontos ja lidos e mantendo o fator anterior.
    """
    pino_botao = BOTAO_CALIBRAR1 if balanca == 1 else BOTAO_CALIBRAR2

    estado_atual = GPIO.input(pino_botao)
    agora = time.monotonic()

    if estado_atual == BOTAO_PRESSIONADO:
        if estado_anterior != BOTAO_PRESSIONADO:
            _inicio_aperto[balanca] = agora
        elif (
            balanca in _calibracoes
            and balanca not in _cancelada_neste_aperto
            and agora - _inicio_aperto.get(balanca, agora) >= TEMPO_CANCELAR_CALIBRACAO
        ):
            _calibracoes.pop(balanca, None)
            _cancelada_neste_aperto.add(balanca)
            _avisar(
                f"Calibração da balança {balanca} cancelada (botão mantido por "
                f"{TEMPO_CANCELAR_CALIBRACAO} s). O fator anterior foi mantido. Pode soltar o botão."
            )
        return estado_atual

    # Botao solto: so age na borda de soltura
    if estado_anterior != BOTAO_PRESSIONADO:
        return estado_atual

    inicio = _inicio_aperto.pop(balanca, agora)
    if balanca in _cancelada_neste_aperto:
        _cancelada_neste_aperto.discard(balanca)
        return estado_atual
    if agora - inicio >= TEMPO_CANCELAR_CALIBRACAO:
        _avisar(f"Nenhuma calibração da balança {balanca} em andamento para cancelar.")
        return estado_atual

    _registrar_aperto_calibracao(balanca)
    return estado_atual


def _registrar_aperto_calibracao(balanca):
    """Aperto curto: inicia a calibracao ou registra o proximo dos tres pesos."""
    calibracao = _calibracoes.setdefault(
        balanca,
        {"iniciada": False, "leituras": []},
    )

    if not calibracao["iniciada"]:
        calibracao["iniciada"] = True
        calibracao["pesos"] = PESOS_CALIBRACAO_KG[balanca]
        _avisar(
            f"Botão de calibração da balança {balanca} pressionado: calibração iniciada. "
            f"Coloque o 1º peso ({calibracao['pesos'][0]} kg) e aperte novamente. "
            f"Para cancelar, segure o botão por {TEMPO_CANCELAR_CALIBRACAO} s."
        )
        return

    numero_ponto = len(calibracao["leituras"])
    peso_atual = calibracao["pesos"][numero_ponto]

    try:
        leitura = bl.retarar_balanca(balanca)
    except (TimeoutError, ValueError, RuntimeError) as erro:
        _avisar(
            f"Erro ao ler a balança {balanca} no {numero_ponto + 1}º peso: {erro}. "
            "Aperte o botão novamente para repetir este ponto."
        )
        return

    calibracao["leituras"].append(float(leitura))

    if numero_ponto < 2:
        proximo = calibracao["pesos"][numero_ponto + 1]
        _avisar(
            f"Balança {balanca}: {numero_ponto + 1}º peso ({peso_atual} kg) registrado. "
            f"Coloque o próximo peso ({proximo} kg) e aperte novamente."
        )
        return

    pesos = np.asarray(calibracao["pesos"], dtype=float)
    leituras = np.asarray(calibracao["leituras"], dtype=float)
    fator, tara = np.polyfit(pesos, leituras, 1)

    if not np.isfinite(fator) or fator == 0:
        _avisar(f"Falha na calibração da balança {balanca}: fator inválido.")
    elif atualizar_fator_config(balanca, fator):
        bl.salvar_tara(balanca, tara)
        BALANCAS[balanca]["fator"] = fator
        _avisar(f"Balança {balanca} recalibrada com sucesso (fator {fator:.3f}). Retornando ao ciclo normal.")
    else:
        _avisar(f"Falha ao salvar o fator da balança {balanca}.")

    _calibracoes.pop(balanca, None)


if __name__ == "__main__":
    mt.setup_todos_os_motores()
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(PINO_BOTAO_MANUAL_MOTOR1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
