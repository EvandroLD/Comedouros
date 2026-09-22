import datetime as dt
import RPi.GPIO as GPIO
import pigpio


# --- Sensor de reflexivo ---
SENSOR_1_PIN = 40
SENSOR_2_PIN = 38
SENSOR_1_PRESENCA_NIVEL = GPIO.HIGH
SENSOR_2_PRESENCA_NIVEL = GPIO.HIGH
SENSOR_1_PULL_UP_DOWN = GPIO.PUD_UP
SENSOR_2_PULL_UP_DOWN = GPIO.PUD_UP
SENSOR_1_CONFIRMATION_TIME = 0.5
SENSOR_1_RELEASE_CONFIRMATION_TIME = 1.0
SENSOR_2_RELEASE_CONFIRMATION_TIME = 1.0
SENSOR_1_POLL_INTERVAL = 0.05
SENSOR_2_POLL_INTERVAL = 0.05
SENSOR_2_CONFIRMATION_TIME = 0.5
TEMPO_ESPERA_RETORNO_ANIMAL = 30

# --- CONFIGURAÇÕES DE HARDWARE (PINOS GPIO BOARD) ---
PINO_RELE = 10
PINO_PWM = 12 
PINO_BOTAO_MANUAL_MOTOR1 = 36
PINO_BOTAO_MANUAL_MOTOR2 = 26
BOTAO_PRESSIONADO = GPIO.HIGH
BOTAO_SOLTO = GPIO.LOW
BOTAO_CALIBRAR1 = 24
BOTAO_CALIBRAR2 = 32

# --- CONFIGURAÇÕES DO LEITOR RFID ---
RFID_PORTA_SERIAL = "/dev/ttyUSB0"
RFID_BAUDRATE = 38400
RFID_POTENCIA_DB = 15
TAGS_RFID_IGNORADAS = {
    "0E8A3000E2801191A50400721456F326",
}

# --- CONFIGURAÇÕES DA BALANCA ---
BALANCAS = {
        1: {"DT": 15, "SCK": 13, "fator": -136833.195, "tara": 0},  # Balança da ração
        2: {"DT": 7, "SCK": 11, "fator": -7228.267, "tara": 0},   # Balança do animal
    }

# Pesos conhecidas usadas nos tres apertos do botao de recalibracao, em kg.
# Altere estes valores para corresponder aos pesos realmente colocados.
PESOS_CALIBRACAO_KG = {
    1: (0.1, 0.2, 0.3),
    2: (1.0, 2.0, 3.0),
}


# --- Dados Relatorio cocho csv ---

#autorizações para acesar os serviços
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


LOCAL_RELATORIO_CSV = "/home/raspberry/comedouros-automaticos_2.0/core/relatorio_cocho.csv"
LOCAL_CREDENCIAL = "/home/raspberry/comedouros-automaticos_2.0/core/SheetsKey.json"
NOME_PLANILHA = "Relatorio_Cocho" 

# --- Dados tag_info.csv ---

TAG_INFO_CSV = "/home/raspberry/comedouros-automaticos_2.0/core/tag_info.csv"
