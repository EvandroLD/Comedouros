import maquina_estados as maq_es
import time
import sensor_reflexivo as sr
import relatorio as rl
import pandas as pd
from config import *
import threading
import botoes_manual as btm
import motor as mt
import sys
import notificacoes as nt

parar = threading.Event() #sistema para desligar todas as threads



def rodar_ciclos(sistemaCocho):
    ultima_recal = 0   
    ultimo_log_pesos = 0
    while not parar.is_set(): #loop principal

        if time.monotonic() - ultimo_log_pesos >= 1:
            sistemaCocho.logar_pesos_reais()
            ultimo_log_pesos = time.monotonic()

        if time.monotonic() - ultima_recal > 30:     # a cada 30s
            sistemaCocho.recalibrar_balanca_sem_presenca() #enquanto não há vacas no cocho, o sistema fica recalibrando a balança
            ultima_recal = time.monotonic()
        
        if sr.confirmar_presenca_sensor('1'): #se tiver vacas no sensor 1, o ciclo se inicia
            print("presença confirmada no sensor 1, entrando no ciclo cocho")
            resposta = sistemaCocho.executar_um_ciclo()
            print(resposta) #retorna os dados sobre o que aconteceu no ciclo.

            #RELATORIO TELEGRAM
            if resposta:
                nt.notificar_relatorio_alimentacao(resposta)
            
            #SHEETS
            if resposta and list(resposta.values())[0]:
                sistemaCocho.relatorio_csv = pd.read_csv(LOCAL_RELATORIO_CSV)
                rl.salvar_registro_csv(sistemaCocho.relatorio_csv, resposta)

                if resposta.get('peso_animal') > -1:
                    sistemaCocho.salvar_peso_animal(resposta['tag_id'], resposta['peso_animal'])

def notificar():
        
    while not parar.is_set():
        rl.sincronizar_csv_com_sheets()
        print(f"enviando csv para sheets")
        parar.wait(30)

def botao():
    estado1 = BOTAO_SOLTO
    estado2 = BOTAO_SOLTO
    estado3 = BOTAO_SOLTO
    estado4 = BOTAO_SOLTO
    buffer_travado1 = []
    buffer_travado2 = [] #deixar bonito depois
    while not parar.is_set():

        estado1 = btm.monitorar_botao_motor(1, estado1)
        estado2 = btm.monitorar_botao_motor(2, estado2)
        estado3 = btm.calibrar(1, estado3)
        estado4 = btm.calibrar(2, estado4)


        mt.destravar(1, buffer_travado1)



def desligar():
    """Para motores e limpa a GPIO. Best-effort, chamado uma vez no fim."""
    parar.set()
    try:
        mt._definir_estado_normal(1, "parado", 0)
        mt._definir_estado_normal(2, "parado", 0)
    except Exception:
        pass
    try:
        GPIO.cleanup()
    except Exception:
        pass
    print("Sistema finalizado.")

if __name__ == "__main__":
    sistemaCocho = maq_es.SistemaCocho()

    try:
        sistemaCocho.configurar_cocho()
        print("\nLeitura inicial das balanças:")
        sistemaCocho.logar_pesos_reais()
    except KeyboardInterrupt:
        desligar()
        sys.exit()
        print(f'Sistema finalizado')

    print("\nIniciando sistema principal()... Pressione Ctrl+C para sair.")
    print("-" * 40)

    t1 = threading.Thread(target=rodar_ciclos, args=(sistemaCocho,), daemon = True)
    t2 = threading.Thread(target=notificar, args=(), daemon= True)
    t3 = threading.Thread(target=botao, args=(), daemon = True)

# Iniciando as threads

    t1.start()
    t2.start()
    t3.start()

    try:
        while t1.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f'\nEncerrando')

    parar.set()
    t1.join(timeout=3)
    t2.join(timeout=3)
    t3.join(timeout=3)
    desligar()