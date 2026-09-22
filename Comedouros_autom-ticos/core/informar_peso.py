from config import *
import pandas as pd
from pathlib import Path
#
#VARIAVEIS:
caminho_csv = Path(__file__).parent / "tag_info.csv"

def cadastrar_peso():

    #PEGO VALORES DO USUÁRIO PARA SALVAR UM REGISTRO NOVO

    tag_id = input("DIGITE O NUMERO DA TAG:").strip()
    peso_ovelha = float(input("DIGITE O VALOR DO PESO DA OVELHA: ").strip())
    #CALCULA O PRECENTUAL COM BASE NO PESO DIGITADO PELO USUARIO
    valor_comida = peso_ovelha * 0.2
    nome = input("DIGITE O NOME DA OVELHA:").strip()
 
    

    #ADICIONA UM REGISTRO NOVO
    novo_registro = {
    "tag_id": tag_id,
    "tipo": "percentual",
    "valor": valor_comida,
    "nome": nome,
    "peso": peso_ovelha,
    "mestra": False
    }


    #CONFERINDO SE EXISTE O CSV E SALVANDO NELE O NOVO REGISTRO
    if caminho_csv.exists():
        dados = pd.read_csv("tag_info.csv")

        dados = pd.concat(
            [dados, pd.DataFrame([novo_registro])],
            ignore_index=True
        )


        #GRAVAÇÃO ACONTECE APENAS AQUI
        dados.to_csv("tag_info.csv", index=False)

    else:
        dados = None
        print("CAMINHO CSV NÃO ENCONTRADO")
        




if __name__ == "__main__":
    cadastrar_peso()
