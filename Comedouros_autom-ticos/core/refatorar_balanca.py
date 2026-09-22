import RPi.GPIO as GPIO
import time
import os
import numpy as np

from config import BALANCAS
from balanca import read_count
from utils_config import atualizar_fator_config

def ler_sensor_suave(dt, sck, amostras=15):
    """Lê o sensor HX711 várias vezes para obter uma média limpa e sem oscilações."""
    soma = 0
    vetor_amostras = []
    for _ in range(amostras):
        vetor_amostras.append(read_count(dt, sck))
        time.sleep(0.1)
    return np.median(vetor_amostras)

def executar_calibracao_multiponto(balanca_id):
    """Guia o produtor pelos 3 passos de calibração via teclado."""
    config = BALANCAS[balanca_id]
    dt_pin = config["DT"]
    sck_pin = config["SCK"]
    nome_balanca = "do ANIMAL" if balanca_id == 2 else "da RAÇÃO"
    
    GPIO.setup(sck_pin, GPIO.OUT)
    GPIO.setup(dt_pin, GPIO.IN)
    
    os.system('clear' if os.name == 'posix' else 'cls')
    print("="*50)
    print(f" INICIANDO CALIBRAÇÃO DA BALANÇA {balanca_id} ({nome_balanca}) ")
    print("="*50)
    
    print("\n" + "-"*50)
    input(" AÇÃO: Remova TUDO de cima da balança, deixe-a VAZIA e pressione ENTER...")
    print(" Lendo tara...")
    time.sleep(1.5)
    
    tara = ler_sensor_suave(dt_pin, sck_pin, amostras=20)
    print(f"TARA REGISTRADA: {tara:.2f}")
    
    fatores = []
    
    # Colocar os Pesos e Digitar o Valor

    for i in range(1, 5): # Vai repetir 10 vezes
        print("\n" + "-"*50)
        
        # Fica em loop até o usuário digitar um número válido
        while True:
            try:
                peso_str = input(f" AÇÃO: Coloque o {i}º peso na balança e DIGITE O VALOR DELE e aperte ENTER: ")
                
                # Troca vírgula por ponto para evitar erros de conversão no Python
                peso_str = peso_str.replace(',', '.')
                peso = float(peso_str)
                
                if peso <= 0:
                    print(" O peso precisa ser maior que zero. Tente novamente.")
                    continue
                break 
                
            except ValueError:
                print(" Valor inválido. Digite apenas números (exemplo: 2.5 ou 10).")
        
        print(" Peso confirmado! Lendo balança...")
        time.sleep(1.5) 
        for k in range(1, 15):
            leitura_bruta = ler_sensor_suave(dt_pin, sck_pin, amostras=15)
            fator_calculado = (leitura_bruta - tara) / peso
            fatores.append(fator_calculado)
            print(f"Leitura bruta: {leitura_bruta:.2f} | Fator parcial: {fator_calculado:.3f}")

# salvamento

    fator_final_medio = sum(fatores) / len(fatores)
    
    print("\n" + "="*50)
    print(" CALIBRAÇÃO FINALIZADA COM SUCESSO! ")
    print(f" Fator Final (Média dos 3 pontos): {fator_final_medio:.3f}")
    print("="*50)
    
    # Atualiza o arquivo config.py automaticamente
    sucesso = atualizar_fator_config(balanca_id, fator_final_medio) 
    
    if sucesso:
        print("\n O novo fator foi salvo no sistema!")
        print("Pode retirar os pesos. A balança já está pronta para uso.")
    else:
        print("\n Erro ao salvar configuração.")

def menu_principal():
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print("==========================================")
        print("   SISTEMA DE RECALIBRAÇÃO DO PRODUTOR    ")
        print("==========================================")
        print("1 - Recalibrar a Balança da Ração (Balança 1)")
        print("2 - Recalibrar a Balança do Animal (Balança 2)")
        print("3 - Sair")
        print("==========================================")
        
        opcao = input("Digite a opção desejada e aperte ENTER: ")
        
        if opcao == '1':
            executar_calibracao_multiponto(1)
            input("\nPressione ENTER para voltar ao menu...")
        elif opcao == '2':
            executar_calibracao_multiponto(2)
            input("\nPressione ENTER para voltar ao menu...")
        elif opcao == '3':
            print("Saindo...")
            break
        else:
            print("Opção inválida!")
            time.sleep(1)

if __name__ == "__main__":
    try:
        GPIO.setmode(GPIO.BOARD)
        menu_principal()
    except KeyboardInterrupt:
        print("\nPrograma interrompido.")
    finally:
        GPIO.cleanup()
