from config import *
import sensor_reflexivo as sr
import time
import leitor_fonkan as rfid
import pandas as pd
import motor
import balanca as bl
import numpy as np
import botoes_manual as btm
import notificacoes as nt 
import traceback
from verificar_intervalo_alimentacao import verificar_intervalo_alimentacao

class SistemaCocho:
    def __init__(self):
        self.leitor_rfid = None
        self.tag_info = None
        self.peso_racao_buffer = []
        self.relatorio_csv = None


        

    def configurar_cocho(self):
        try:
            sr.setup_gpio() # setando gpios do sensor
            btm.setup_botoes() 
            self.leitor_rfid = rfid.iniciar_leitor()
            self.tag_info = pd.read_csv(TAG_INFO_CSV)
            self.relatorio_csv = pd.read_csv(LOCAL_RELATORIO_CSV)
            motor.setup_todos_os_motores()
            motor._definir_estado_normal(2, "horario", 255)
            time.sleep(7)
            motor._definir_estado_normal(2, "parado", 0)
            for num, config in BALANCAS.items():
                bl.setup_balanca(config["DT"], config["SCK"])
                bl.calibrar_balanca(num)    

        except Exception as e:
            print(f"erro na configuração do sistema: {e}")

    def recalibrar_balanca_sem_presenca(self):
        """
        recalibra a balança se ninguém estiver em cima. para casos quando o sistema já está rodando.
        """
        if (not sr.sensor_tem_presenca('1')) and (not sr.sensor_tem_presenca('2')):
            for num in BALANCAS.keys():
                try:
                    tara = bl.retarar_balanca(num)
                    if (not sr.sensor_tem_presenca('1')) and (not sr.sensor_tem_presenca('2')):
                        bl.salvar_tara(num, tara)
                        print(f'tara da balança{num} foi salva')
                except (TimeoutError, ValueError, RuntimeError) as erro:
                    print(f"Falha ao recalibrar a balanca {num}: {erro}")

    def salvar_peso_animal(self, tag, peso):
        if peso and peso > 0:
            self.tag_info.loc[self.tag_info['tag_id'] == tag, 'peso'] = round(peso, 2)
            self.tag_info.to_csv(TAG_INFO_CSV, index=False)
            self.tag_info = pd.read_csv(TAG_INFO_CSV)

    def logar_pesos_reais(self):
        peso1, bruto1 = bl.ler_peso(1)
        peso2, bruto2 = bl.ler_peso(2)
        peso1_log = f"{peso1:.3f} kg" if peso1 is not None else "ERRO"
        peso2_log = f"{peso2:.3f} kg" if peso2 is not None else "ERRO"
        print(
            f"[BALANCAS] Balança 1: {peso1_log} (bruto: {bruto1}) | "
            f"Balança 2: {peso2_log} (bruto: {bruto2})"
        )

    def _aguardar_retorno_animal(self):
        """Espera o animal voltar ao sensor antes de encerrar a alimentação."""
        inicio_espera = time.monotonic()

        print(
            f"Animal saiu do sensor; aguardando retorno por "
            f"{TEMPO_ESPERA_RETORNO_ANIMAL} segundos."
        )

        while time.monotonic() - inicio_espera < TEMPO_ESPERA_RETORNO_ANIMAL:
            if sr.confirmar_presenca_sensor('1'):
                print("Animal retornou ao sensor; continuando a alimentação.")
                return True
            time.sleep(SENSOR_1_POLL_INTERVAL)

        print("Tempo de retorno esgotado; finalizando a alimentação.")
        return False

    def executar_um_ciclo(self):        
        """
        Roda apenas UMA vez o ciclo completo de um animal.
        Retorna um dicionário com o que aconteceu para o main.py.
        """

        tag = nome_animal = saida = peso_racao_despejada = minutos = segundos = peso_animal_atual = 0
        self.peso_racao_buffer = []
        peso_animal_buffer = []
        peso_racao_despejada = 0
        entrada = time.ctime()
        inicio = time.monotonic()

        self.logar_pesos_reais()
        
        try:
            
            while sr.confirmar_presenca_sensor('1'): #começa confirmando a presença do animal

                tag = rfid.normalizar_tag_id(
                    rfid.ler_tags(
                        self.leitor_rfid,
                        timeout=5,
                        tags_ignoradas=TAGS_RFID_IGNORADAS,
                    )
                )  # tenta ler o RFID enquanto o animal estiver presente

                if tag: #se achou o rfid
                    print(f"tag lida: {tag}")

<<<<<<< Updated upstream
                    if tag in self.tag_info['tag_id'].values: #vê se a tag ta no .csv
=======
		    #TAG FANTASMA 
                    if tag == '0E8A3000E2801191A50400721456F326':
                        print(f"TAG FANTASMA FOI LIDA")
                        ####EU DUVIDO QUE ISSO FUNCIONA PARA IGNORAR A TAG, MAS EU DUVIDO!!!!!!!!!!!!!!!!######
                        continue

                    else:
                        
                        print(f"tag lida: {tag}")


                        #CONFERIR SE ISSSO FUNCIONA !!!!!!!!!!!!!!!!!!!!!!!!!
                        if tag in self.tag_info['tag_id'].values: #vê se a tag ta no .csv
                            nome_animal = self.tag_info.loc[
                                self.tag_info['tag_id'] == tag, 'nome'
                            ].values[0]
>>>>>>> Stashed changes

                            if verificar_intervalo_alimentacao(tag, LOCAL_RELATORIO_CSV):
                                print(
                                    f"Tag {tag} bloqueada: já se alimentou "
                                    "nas últimas 24 horas."
                                )
                                nt.notificar_bloqueio_alimentacao(tag)
                                sr.aguardar_sensor_livre('1')

                                saida = time.ctime()
                                segundos_no_cocho = time.monotonic() - inicio
                                minutos = int(segundos_no_cocho // 60)
                                segundos = int(segundos_no_cocho % 60)
                                #CONFERIR SE ISSSO FUNCIONA !!!!!!!!!!!!!!!!!!!!!!!!!
                                return {
                                    'tag_id': tag,
                                    'nome': nome_animal,
                                    'hora_entrada': entrada,
                                    'hora_saida': saida,
                                    'tempo_cocho': (
                                        f"{minutos}m {segundos:02d}s"
                                        if minutos != 0 or segundos != 0 else 0
                                    ),
                                    'peso_animal': 0,
                                    'peso_racao': -2
                                }

                            ##TELEGRAM  ALERTA
                            nt.notificar_subida_animal(tag)

<<<<<<< Updated upstream
                            peso_racao = pd.to_numeric(
                                self.tag_info.loc[
                                    self.tag_info['tag_id'] == tag, 'valor'
                                ].values[0],
                                errors='coerce',
                            )  # pega o peso da ração no .csv
                            if pd.isna(peso_racao) or peso_racao <= 0:
                                print(
                                    f"Valor de racao invalido para a tag {tag}; "
                                    "ciclo cancelado."
                                )
                                sr.aguardar_sensor_livre('1')
                                return None
                            nome_animal = self.tag_info.loc[self.tag_info['tag_id'] == tag, 'nome'].values[0]
=======
                            peso_racao = self.tag_info.loc[self.tag_info['tag_id'] == tag, 'valor'].values[0] #pega o peso da ração no .csv
>>>>>>> Stashed changes
                            peso_animal_anterior = self.tag_info.loc[self.tag_info['tag_id'] == tag, 'peso'].values[0]
                            tipo_racao = self.tag_info.loc[self.tag_info['tag_id'] == tag, 'tipo'].values[0]
                                
                            print(f"tag encontrada, a vaquinha {nome_animal} vai comer {peso_racao}kg de ração hoje!")

                        # if tipo_racao == 'percentual' and not pd.isna(peso_animal):
                                #altera peso_racao para ser a porcentagem do animal
                        # elif tipo_racao == 'percentual':
                                #coloca peso como valor fixo padrao

                            #começa a rodar o motor e ler balanca 3. ALIMENTAÇÃO (Motor/Balança)
                            while True:
                                self.logar_pesos_reais()

                                if not sr.confirmar_presenca_sensor('1'):
                                    motor._definir_estado_normal(1, "parado", 0)
                                    if not self._aguardar_retorno_animal():
                                        break

                                peso1, _ = bl.ler_peso(1)
                                if peso1 is not None:
                                    self.peso_racao_buffer.append(peso1)

                                if len(self.peso_racao_buffer) > 10:
                                    self.peso_racao_buffer.pop(0)
                                    print(f'lendo peso despejado {peso_racao_despejada}')
                                    if (peso_racao_despejada:= np.median(self.peso_racao_buffer)) > peso_racao:
                                        print(f'{peso_racao_despejada} > {peso_racao}')
                                        break
                                if (peso_racao_despejada > (0.7*peso_racao)):
                                    print(f'{peso_racao_despejada} > 0.7* {peso_racao}')
                                    motor._definir_estado_normal(1,"horario", 80)
                                else:
                                    motor._definir_estado_normal(1,"horario", 150)


                            motor._definir_estado_normal(1, "parado", 0)

                            motor._definir_estado_normal(2, "horario", 255)

                            for _ in range(10):
                                self.logar_pesos_reais()
                                peso2,_ = bl.ler_peso(2)
                                if peso2 is not None:
                                    peso_animal_buffer.append(peso2)

                            if len(peso_animal_buffer) >= 3:
                                peso_animal_atual = np.median(peso_animal_buffer)
                                if pd.notna(peso_animal_anterior) and abs(peso_animal_atual - peso_animal_anterior) / peso_animal_anterior > 0.20:
                                    print(f'peso medido {peso_animal_atual:.1f} desviou >20% de {peso_animal_anterior:.1f}, descartando')
                                    peso_animal_atual = -1
                            else:
                                print('poucas leituras validas da balanca 2, usando peso anterior')
                                peso_animal_atual = -1

                            time.sleep(7)
                            motor._definir_estado_normal(2, "parado", 0)

                            sr.aguardar_sensor_livre('1')
                            saida = time.ctime()
                            fim = time.monotonic()
                            segundos_no_cocho = fim - inicio
                            minutos = int(segundos_no_cocho // 60)
                            segundos = int(segundos_no_cocho % 60)
                            break

                    elif tag:
                        print(
                            f"Tag {tag} não foi encontrada no sistema csv; "
                            "aguardando uma tag cadastrada."
                        )
                        continue
        except Exception as e:
            print(f"Erro no sistema principal: {e}")
            traceback.print_exc()
            return None

        if not tag:
            return None

        return {
            'tag_id': tag,
            'nome': nome_animal,
            'hora_entrada' : entrada,
            'hora_saida' : saida,
            'tempo_cocho' : f"{minutos}m {segundos:02d}s" if minutos != 0 or segundos != 0 else 0,
            'peso_animal' : round(peso_animal_atual, 3),
            'peso_racao' : round(peso_racao_despejada, 3)
        }

if __name__ == "__main__":
    try:
        sistemaCocho = SistemaCocho()
        print("\nIniciando o teste da função principal()... Pressione Ctrl+C para sair.")
        print("-" * 40)
        sistemaCocho.configurar_cocho()
        while True:
            resposta = sistemaCocho.executar_um_ciclo()
            if resposta is not None:
                print(resposta)               
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nPrograma encerrado pelo usuário.")
    finally:
        sr.GPIO.cleanup()
        print("Configurações da GPIO limpas.")
