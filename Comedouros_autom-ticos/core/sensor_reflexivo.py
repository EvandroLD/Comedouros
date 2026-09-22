# main.py
import RPi.GPIO as GPIO
import time
from config import *
from datetime import datetime

SENSORES = {
    SENSOR_1_PIN: f"Sensor 1 (Pino {SENSOR_1_PIN})",
    SENSOR_2_PIN: f"Sensor 2 (Pino {SENSOR_2_PIN})"
}

STATUS_LIVRE = "Caminho livre"
STATUS_BLOQUEADO = "!!! OBJETO DETECTADO !!!"
SENSOR_PRESENCA_NIVEL = {
    SENSOR_1_PIN: SENSOR_1_PRESENCA_NIVEL,
    SENSOR_2_PIN: SENSOR_2_PRESENCA_NIVEL,
}
SENSOR_PULL_UP_DOWN = {
    SENSOR_1_PIN: SENSOR_1_PULL_UP_DOWN,
    SENSOR_2_PIN: SENSOR_2_PULL_UP_DOWN,
}

def setup_gpio():
    """Configura o modo da GPIO e os pinos dos sensores como entrada."""
    GPIO.setmode(GPIO.BOARD)
    
    for pin in SENSORES:
        GPIO.setup(pin, GPIO.IN, pull_up_down=SENSOR_PULL_UP_DOWN[pin])
    print("GPIO configurada com sucesso.")


def sensor_tem_presenca(sensor, logger=None):
    pin = SENSOR_1_PIN if sensor == '1' else SENSOR_2_PIN

    try:
        return GPIO.input(pin) == SENSOR_PRESENCA_NIVEL[pin]
    except Exception as exc:
        if logger:
            logger.error(f"Erro ao ler sensor no pino {pin}. Considerando sem presenca: {exc}", exc_info=True)
        return False



def confirmar_presenca_sensor(sensor, logger=None):

    confirmation_time = SENSOR_1_CONFIRMATION_TIME if sensor == '1' else SENSOR_2_CONFIRMATION_TIME
    poll_interval = SENSOR_1_POLL_INTERVAL if sensor == '1' else SENSOR_2_POLL_INTERVAL

    inicio = time.monotonic()
    fim = inicio + confirmation_time
    logou_inicio = False

    while time.monotonic() < fim:
        if not sensor_tem_presenca(sensor, logger=logger):
            if logou_inicio and logger:
                logger.info("Confirmacao de presenca no Sensor {sensor} cancelada: sinal desapareceu.")
            return False

        if not logou_inicio:
            if logger:
                logger.info(
                    f"Confirmacao de presenca no Sensor {sensor} iniciada "
                    f"({confirmation_time:.2f}s)."
                )
            logou_inicio = True

        time.sleep(poll_interval)

    if logger:
        logger.info("Presenca confirmada no Sensor {sensor}.")
    return True


def aguardar_sensor_livre(sensor, logger=None):
    inicio_livre = None
    ultimo_log = 0

    release_confirmation_time = SENSOR_1_RELEASE_CONFIRMATION_TIME if sensor == '1' else SENSOR_2_RELEASE_CONFIRMATION_TIME
    pin = SENSOR_1_PIN if sensor == '1' else SENSOR_2_PIN
    presenca_nivel = SENSOR_1_PRESENCA_NIVEL if sensor == '1' else SENSOR_2_PRESENCA_NIVEL
    poll_interval = SENSOR_1_POLL_INTERVAL if sensor == '1' else SENSOR_2_POLL_INTERVAL

    while True:
        agora = time.monotonic()

        if not sensor_tem_presenca(sensor,logger=logger):
            if inicio_livre is None:
                inicio_livre = agora

            if agora - inicio_livre >= release_confirmation_time:
                if logger:
                    logger.info("Sensor {sensor} livre confirmado.")
                return True
        else:
            inicio_livre = None
            if logger and agora - ultimo_log >= 5:
                nivel_atual = GPIO.input(pin)
                logger.warning(
                    f"Sensor {sensor} ainda indica presenca no pino {pin} "
                    f"(nivel atual: {nivel_atual}, nivel de presenca configurado: "
                    f"{presenca_nivel}). Aguardando liberar antes do RFID."
                )
                ultimo_log = agora

        time.sleep(poll_interval)

def aguardar_sensores_livres(logger=None):
    """
    Aguarda até que os Sensores 1 e 2 estejam simultaneamente livres
    por um tempo contínuo de segurança.
    """
    inicio_livre = None
    ultimo_log = 0

    # Adota o maior tempo de confirmação entre os dois sensores para garantir segurança total
    release_confirmation_time = max(SENSOR_1_RELEASE_CONFIRMATION_TIME, SENSOR_2_RELEASE_CONFIRMATION_TIME)
    
    # Adota o menor intervalo de checagem para responder mais rápido
    poll_interval = min(SENSOR_1_POLL_INTERVAL, SENSOR_2_POLL_INTERVAL)

    while True:
        agora = time.monotonic()

        # Tira uma "foto" do estado dos dois sensores no mesmo instante
        tem_presenca_1 = sensor_tem_presenca('1', logger=logger)
        tem_presenca_2 = sensor_tem_presenca('2', logger=logger)

        # Só começa/continua a contar o tempo se AMBOS estiverem livres
        if not tem_presenca_1 and not tem_presenca_2:
            
            if inicio_livre is None:
                inicio_livre = agora

            # Se o tempo contínuo de pista limpa atingir o limite, libera o código
            if agora - inicio_livre >= release_confirmation_time:
                if logger:
                    logger.info("Pista limpa: Ambos os sensores livres confirmados simultaneamente.")
                return True
        else:
            # Se QUALQUER sensor detectar algo, zera o cronômetro! (Resolve o "ping-pong")
            inicio_livre = None
            
            # Log de aviso a cada 5 segundos para não flodar o console
            if logger and agora - ultimo_log >= 5:
                # Descobre quem está travando a pista para avisar no log
                culpados = []
                if tem_presenca_1: culpados.append("Sensor 1")
                if tem_presenca_2: culpados.append("Sensor 2")
                
                logger.warning(
                    f"Aguardando liberação total. Bloqueio detectado em: {' e '.join(culpados)}. "
                    f"Aguardando a pista inteira esvaziar."
                )
                ultimo_log = agora

        time.sleep(poll_interval)        





def ler_sensores():
    """
    Lê o estado de todos os sensores configurados e retorna um dicionário com os resultados.

    Returns:
        dict: Um dicionário onde a chave é o nome do sensor e o valor é seu estado
              (ex: 'Caminho livre' ou '!!! OBJETO DETECTADO !!!').
    """
    estados_atuais = {}
    
    for pin, name in SENSORES.items():
        pin1 = '1' if pin == SENSOR_1_PIN else '2'
        if sensor_tem_presenca(pin1):
            status = STATUS_BLOQUEADO
        else:
            status = STATUS_LIVRE
        
        estados_atuais[name] = status
        
    return estados_atuais


'''def aguardar_confirmacao_de_posicao(logger, tag_id):
        """
        Aguarda a confirmação de que o animal está posicionado entre os dois sensores,
        utilizando a função ler_sensores() que retorna um dicionário.
        """
        logger.info(f"[{tag_id}] Aguardando animal se posicionar (método: dicionário)...")

        tempo_limite_confirmacao = 5
        inicio_espera = time.time()
        
        CHAVE_SENSOR_ENTRADA = f"Sensor 1 (Pino {SENSOR_1_PIN})"
        CHAVE_SENSOR_SAIDA = f"Sensor 2 (Pino {SENSOR_2_PIN})"
        while time.time() - inicio_espera < tempo_limite_confirmacao:
            estados_sensores = ler_sensores()
            
            logger.debug(f"   -> Dicionário recebido: {estados_sensores}")

            status_entrada = estados_sensores.get(CHAVE_SENSOR_ENTRADA)
            status_saida = estados_sensores.get(CHAVE_SENSOR_SAIDA)

            if status_entrada == STATUS_BLOQUEADO and status_saida != STATUS_BLOQUEADO:
                logger.info(f"ANIMAL POSICIONADO! Confirmação pelos sensores de entrada e saída.")
                return True

            time.sleep(0.2)
        
        logger.warning(f"[{tag_id}] Tempo esgotado. O animal não se posicionou corretamente.")
        return False'''


if __name__ == "__main__":
    try:
        setup_gpio()
        
        print("\nIniciando o teste da função ler_sensores()... Pressione Ctrl+C para sair.")
        print("-" * 40)
        
        while True:
            estados_dos_sensores = ler_sensores()
            
            print(f"Dados retornados pela função: {estados_dos_sensores}")
            
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nPrograma encerrado pelo usuário.")
    finally:
        GPIO.cleanup()
        print("Configurações da GPIO limpas.")
