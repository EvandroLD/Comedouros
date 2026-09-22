# leitor_fonkan.py
import serial
import time
import pandas as pd
import os
from reader import Reader
from config import (
    RFID_PORTA_SERIAL,
    RFID_BAUDRATE,
    RFID_POTENCIA_DB,
    TAGS_RFID_IGNORADAS,
)


def normalizar_tag_id(tag_id):
    if tag_id is None:
        return None
    return str(tag_id).strip().upper()

def ajustar_potencia(leitor, potencia_db):
    """Ajusta a potência de leitura do módulo RFID."""
    valor_hex = hex(potencia_db + 2)[2:].upper().zfill(2)
    comando = f"\nN1,{valor_hex}\r".encode("utf-8")
    leitor.ser.write(comando)
    time.sleep(0.3)
    leitor.ser.reset_input_buffer()
    leitor.ser.reset_output_buffer()

def iniciar_leitor():
    """Inicia e configura o leitor RFID."""
    try:
        print(f" Conectando à {RFID_PORTA_SERIAL} a {RFID_BAUDRATE} bps...")
        ser = serial.Serial(RFID_PORTA_SERIAL, RFID_BAUDRATE, timeout=1)
        print(" Porta serial aberta.")
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        leitor = Reader(ser)
        ajustar_potencia(leitor, RFID_POTENCIA_DB)
        print(f" Potência ajustada para {RFID_POTENCIA_DB} dB.\n")
        return leitor
    except Exception as e:
        print(f" Erro ao iniciar leitor: {e}")
        return None

def ler_tags(leitor, timeout=5, tags_ignoradas=TAGS_RFID_IGNORADAS):
    """
    Lê uma única tag dentro de um tempo limite e retorna seu ID.

    Args:
        leitor: O objeto do leitor RFID.
        timeout (int): O tempo máximo em segundos para tentar a leitura.

    Returns:
        str: A ID da tag lida, ou None se o tempo esgotar ou ocorrer um erro.
    """
    try:
        if leitor is None:
            print(" Leitor RFID não inicializado.")
            return None

        print(f" Aproxime a tag do leitor... (timeout de {timeout} segundos)\n")
        leitor.clear_serial_buffers()
        
        inicio_leitura = time.time()

        while time.time() - inicio_leitura < timeout:
            try:
                tags = leitor.multi_tag_EPC_read()
            except Exception as e:
                print(f"Erro na comunicação com o leitor RFID: {e}")
                leitor.clear_serial_buffers()
                time.sleep(0.2)
                continue

            if tags:
                for tag in tags:
                    raw_data = tag[0]
                    tag_id = normalizar_tag_id("".join(f"{word:04X}" for word in raw_data))
                    if tag_id in tags_ignoradas:
                        print(f" Tag RFID ignorada: {tag_id}")
                        continue
                    print(f" Tag lida: {tag_id}")
                    return tag_id
            time.sleep(0.1)
            
        print(" Tempo esgotado. Nenhuma tag foi lida.")
        return None

    except Exception as e:
        print(f"Erro ao ler tag: {e}")
        return None

def getTagInfo(csv, tag):
    filtro = csv[csv['tag_id'] == tag]

    
    if not filtro.empty:
        resultado = filtro.iloc[0].to_dict()
        return resultado
    else:
        return None

def autualizarTag(csv, tag):   
        
        while True:
            if resultado := getTagInfo(csv, tag):
                print("Esta tag já existe no sistema, deseja autualizar alguma informação dela?\n")
                ex_nome = resultado['nome']
                ex_valor = resultado['valor']
                ex_mestra = resultado['mestra']
                ex_peso = resultado['peso']
                opcao = input(f'1- Nome: {ex_nome} \n2- Valor: {ex_valor}\n3- Peso para o animal: {ex_peso}\n4- Permissão mestra: {ex_mestra}\n')
                match opcao:
                    case '1':
                        while True:
                            nome = input('digite um nome para a tag\n').strip()
                            if nome:
                                break
                            else:
                                print("Digite algo!")
                        csv.loc[csv['tag_id'] == tag, 'nome'] = nome
                        csv.to_csv('tag_info.csv', index=False)
                    case '2':
                        while True:
                            valor = input('quantos gramas de ração por dia?\n').strip()
                            try:
                                numero = float(valor)
                                break
                            except ValueError:
                                print("entrada inválida, digite apenas números!!")
                        csv.loc[csv['tag_id'] == tag, 'valor'] = valor
                        csv.to_csv('tag_info.csv', index=False)
                    case '3':
                        while True:
                            peso = input('quantos quilos o animal está pesando?\n').strip()
                            try:
                                numero = float(peso)
                                break
                            except ValueError:
                                print("entrada inválida, digite apenas números!!")
                        csv.loc[csv['tag_id'] == tag, 'peso'] = peso
                        csv.to_csv('tag_info.csv', index=False)
                    case '4':
                        while True:
                            mestra = input('essa chave é mestra? Digite apenas "s" ou "n"\n')
                            if mestra == 's':
                                mestra = True
                                break
                            if mestra == 'n':
                                mestra = False
                                break
                        csv.loc[csv['tag_id'] == tag, 'mestra'] = mestra
                        csv.to_csv('tag_info.csv', index=False)

                input("pressione enter para voltar ou cntrl + c para sair")
        
            else:
                print("iniciando processo para cadastro da tag:")
                while True:
                    nome = input('digite um nome para a tag\n').strip()
                    if nome:
                        break
                    else:
                        print("Digite algo!")
                
                while True:
                    valor = input('quantos gramas de ração por dia?\n').strip()
                    try:
                        numero = float(valor)
                        break
                    except ValueError:
                        print("entrada inválida, digite apenas números!!")
                while True:
                    peso = input('Qual o peso do animal?\n').strip()
                    try:
                        numero = float(peso)
                        break
                    except ValueError:
                        print("entrada inválida, digite apenas números!!")
                while True:
                    mestra = input('essa chave é mestra? Digite apenas "s" ou "n"\n')
                    if mestra == 's':
                        mestra = True
                        break
                    if mestra == 'n':
                        mestra = False
                        break

                nova_tag = pd.DataFrame([{
                    'tag_id': tag,
                    'tipo' : 'fixo',
                    'valor' : numero,
                    'nome' : nome,
                    'peso' : peso,
                    'mestra' : mestra
                }])

                csv = pd.concat([csv, nova_tag], ignore_index=True)
                csv.to_csv('tag_info.csv', index = False)

                print("tag cadastrada com sucesso!")

            return nova_tag.iloc[0].to_dict()

def exibir_menu():
    """Mostra o menu de opções para o usuário."""
    os.system('clear' if os.name == 'posix' else 'cls')
    print("===================================")
    print("   Gerenciador de Tags RFID")
    print("===================================")
    print("1. Tag info")
    print("2. Registrar nova tag (ou atualizar)")
    print("3. Sair")
    print("-----------------------------------")
    return input("Escolha uma opção: ")


if __name__ == "__main__":

    csv = pd.read_csv('tag_info.csv')
    leitor_rfid = iniciar_leitor()
    while True:
        opcao = exibir_menu()
        match opcao:

            case "1":
                tag = ler_tags(leitor_rfid)
                if (resultado := getTagInfo(csv, tag)):
                    print(resultado)
                elif tag:
                    print(f"a tag {tag} não está no banco de dados")

            case "2":
                tag = ler_tags(leitor_rfid)
                autualizarTag(csv, tag)
            

        
        input("Pressione enter para voltar")
            





