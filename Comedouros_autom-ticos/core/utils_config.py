import re
import os

CONFIG_PATH = "/home/raspberry/comedouros-automaticos_2.0/core/config.py"

def atualizar_fator_config(balanca_id, novo_fator):
    """
    Lê o arquivo config.py, encontra a definição da BALANCAS e atualiza o fator
    usando Regex para preservar o restante do arquivo.
    """
    try:
        with open(CONFIG_PATH, 'r') as f:
            conteudo = f.read()

        padrao = rf'({balanca_id}:\s*{{.*?[\"\']fator[\"\']:\s*)([-\d\.]+)(.*?}})'
        
        match = re.search(padrao, conteudo, re.DOTALL)
        
        if match:
            novo_trecho = f"{match.group(1)}{novo_fator:.3f}{match.group(3)}"
            novo_conteudo = conteudo.replace(match.group(0), novo_trecho)
            
            with open(CONFIG_PATH, 'w') as f:
                f.write(novo_conteudo)
            return True
        else:
            print(f"Erro: Não foi possível encontrar a configuração da balança {balanca_id} no arquivo.")
            return False
            
    except Exception as e:
        print(f"Erro ao atualizar config.py: {e}")
        return False