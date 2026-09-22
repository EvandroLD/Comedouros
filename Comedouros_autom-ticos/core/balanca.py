import RPi.GPIO as GPIO
import time
import numpy as np
from config import *
import csv
import os
import grafico_maker



TIMEOUT_LEITURA_HX711_SEGUNDOS = 2
VALOR_HX711_MINIMO = 1
VALOR_HX711_MAXIMO = 0xFFFFFF - 1

#configura os pinos GPIO para uma balanca
def setup_balanca(dt, sck):
    # O initial=GPIO.LOW impede que o sensor entre em modo de suspensão
    GPIO.setup(sck, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(dt, GPIO.IN)
    time.sleep(0.1) # Dá um fôlego para o sensor ligar


#apenas para ler o HX, retorna um numero inteiro de 24 bits
def read_count(dt, sck, timeout=TIMEOUT_LEITURA_HX711_SEGUNDOS):

    #inicia o count para alocar os dados convertidos pelo HX
    count = 0

    #inicia o clock em baixo
    GPIO.output(sck, False)

    #guarda o instante inicial da leitura do sensor
    inicio = time.monotonic()

    #tenta ler o dado do HX, se demorar demais retorna um erro
    while GPIO.input(dt):
        if time.monotonic() - inicio > timeout:
            GPIO.output(sck, False)
            raise TimeoutError(f"Timeout ao ler HX711 (DT={dt}, SCK={sck}).")
        time.sleep(0.0001)

    #le os 24 bits que o HX envia
    for _ in range(24):
        GPIO.output(sck, True)
        GPIO.output(sck, False)
        #desloca os bits para a esquerda para esperar os proximos
        count = count << 1
        if GPIO.input(dt):
            count += 1
    #ligando o HX novamente para ajustar o valor bruto
    GPIO.output(sck, True)
    GPIO.output(sck, False)
    count = count ^ 0x800000

    if not VALOR_HX711_MINIMO <= count <= VALOR_HX711_MAXIMO:
        raise ValueError(f"Leitura HX711 saturada ou invalida: {count}")

    return count

#TRANSFORMA LEITURA BRUTA EM PESO REAL 
def calculo_peso(tara, leitura, fator):
    return (leitura - tara) / fator


#CALIBRA A BALANCA E ENVIA A TARA PARA O CONFIG
def calibrar_balanca(num_balanca):
    """Executa o processo de calibração para uma balança específica."""
    config = BALANCAS[num_balanca]
    dt, sck = config["DT"], config["SCK"]
    
    print(f"\n--- Calibrando Balança {num_balanca} ---")
    print("Por favor, remova todo o peso da balança.")

    print("Estabilizando o sensor...")
    for _ in range(10): # Joga fora as primeiras 10 leituras
        try:
            read_count(dt, sck)
        except:
            pass
        time.sleep(0.1)


    print("Realizando leituras...")
    leituras = []
    for _ in range(20):
        try:
            leituras.append(read_count(dt, sck))
        except (TimeoutError, ValueError) as erro:
            print(f"Leitura invalida na calibracao da balanca {num_balanca}: {erro}")

    if len(leituras) < 5:
        raise RuntimeError(
            f"Poucas leituras validas para calibrar a balanca {num_balanca}."
        )
    
    mediana_tara = np.median(leituras)
        
    BALANCAS[num_balanca]["tara"] = mediana_tara

def retarar_balanca(num_balanca):
    "Retorna a tara do momento em que a função foi chamada, deve ser usada com a função 'salvar tara'"
    config = BALANCAS[num_balanca]
    dt, sck = config["DT"], config["SCK"]
        
    print(f"\n--- recalibrando Balança {num_balanca} ---")
    
    print("Realizando leituras...")
    leituras = []
    for _ in range(20):
        try:
            leituras.append(read_count(dt, sck))
        except (TimeoutError, ValueError) as erro:
            print(f"Leitura invalida ao retarar a balanca {num_balanca}: {erro}")

    if len(leituras) < 5:
        raise RuntimeError(
            f"Poucas leituras validas para retarar a balanca {num_balanca}."
        )
        
    mediana_tara = np.median(leituras)
    return mediana_tara

def salvar_tara(num_balanca,tara):
    "Salva a tara na balança especificada"
    BALANCAS[num_balanca]["tara"] = tara





#CALCULA O PESO REAL USANDO O CALCULO_PESO
def ler_peso(num_balanca):
    """Lê e calcula o peso de uma única balança, usando sua função `calculo_peso`."""
    config = BALANCAS[num_balanca]
    
    if config["tara"] == 0:
        print(f"\nAVISO: Balança {num_balanca} não foi calibrada. Use a opção de calibração primeiro.")
        time.sleep(2)
        return [None, None]
    try:
        leitura_atual = read_count(config["DT"], config["SCK"])
        peso = calculo_peso(config["tara"], leitura_atual, config["fator"])
        return [peso, leitura_atual]
    except Exception as e:
        print(f"erro na leitura hx711: {e}")
        return [None, None]

#FUNCAO PARA TESTAR OS HX
def teste_hx(dt,sck):

    intervalo = 1
    
    GPIO.setmode(GPIO.BOARD)
    setup_balanca(dt, sck)

    print(f"Teste da balança iniciado (DT={dt}, SCK={sck}).")
    print("Pressione Ctrl+C para encerrar.")

    try:
        while True:
            valor_bruto = read_count(dt, sck)
            print(f"VALOR BRUTO:{valor_bruto}")
            time.sleep(intervalo)
    except KeyboardInterrupt:
        print("\nTeste encerrado.")
    finally:
        GPIO.cleanup()

def mediana_buffer(buffer_peso, peso):
    if len(buffer_peso)>5:
        buffer_peso.pop(0)
        buffer_peso.append(peso)
        peso     = np.median(buffer_peso)
        return peso
    else:
        buffer_peso.append(peso)
        return None


#main de teste apenas para ver se estamos recebendo dados do HX
def main():
    # Evita que o terminal fique jogando warnings na tela
    GPIO.setwarnings(False) 
    GPIO.setmode(GPIO.BOARD)
    
    # Configura e calibra todas as balanças automaticamente
    for num, config in BALANCAS.items():
        setup_balanca(config["DT"], config["SCK"])
        calibrar_balanca(num)  
        
    print("\n--- Lendo pesos em tempo real (Ctrl+C para sair) ---")

    leituras = []
    try:
        buffer_peso1 = []
        buffer_peso2 = []
        while True:
            
            peso1, bruto1 = ler_peso(1)
            peso2, bruto2 = ler_peso(2)

            if peso1 is not None:
                peso1 = mediana_buffer(buffer_peso1, peso1)
            if peso2 is not None:
                peso2 = mediana_buffer(buffer_peso2, peso2)

            leituras.append([peso1, bruto1, peso2, bruto2])
            # Garante que não vai dar erro se a leitura falhar
            p1_str = f"{peso1:6.2f} kg" if peso1 is not None else "Erro"
            p2_str = f"{peso2:6.2f} kg" if peso2 is not None else "Erro"
            
            # Formata os valores brutos para mostrar na tela
            b1_str = f"{bruto1}" if bruto1 is not None else "Erro"
            b2_str = f"{bruto2}" if bruto2 is not None else "Erro"

            print(f"\rBalança 1: {p1_str} (Bruto: {b1_str}) | Balança 2: {p2_str} (Bruto: {b2_str})          ", end="", flush=True)
            
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\nEncerrando teste...")
        os.makedirs("balanca_debug", exist_ok=True)  
        caminho_csv = os.path.join("balanca_debug", "leituras_balanca.csv")  
        with open(caminho_csv, "w", newline="") as f: 
            w = csv.writer(f)
            w.writerow(["peso1", "bruto1", "peso2", "bruto2"])
            w.writerows(leituras) 
        grafico_maker.grafico_make(caminho_csv)
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
