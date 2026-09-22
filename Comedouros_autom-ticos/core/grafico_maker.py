"""
ATENÇÃO
ESTE CODIGO FOI FEITO POR IA
USÁ-LO APENAS PARA TESTES
"""

import sys
import os
import matplotlib
matplotlib.use("Agg")                 # sem tela (Raspberry headless)
import matplotlib.pyplot as plt
import pandas as pd

def grafico_make(caminho=None):
    PASTA = "balanca_debug"
    if caminho is None:
        caminho = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PASTA, "leituras_balanca.csv")
    SAIDA = os.path.splitext(caminho)[0] + ".png"   # png ao lado do csv

    os.makedirs(os.path.dirname(SAIDA) or ".", exist_ok=True)

    df = pd.read_csv(caminho)

    # "Erro" / vazio / None viram NaN pra nao quebrar o plot
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    colunas = ["peso1", "bruto1", "peso2", "bruto2"]
    titulos = {
        "peso1": "Peso 1 (ração)",
        "bruto1": "Bruto 1 (ADC)",
        "peso2": "Peso 2 (animal)",
        "bruto2": "Bruto 2 (ADC)",
    }

    fig, axes = plt.subplots(2, 2, figsize=(12, 7))
    for ax, col in zip(axes.flat, colunas):
        ax.plot(df.index, df[col], marker=".", markersize=3, linewidth=0.8)
        ax.set_title(titulos.get(col, col))
        ax.set_xlabel("index da linha")
        ax.set_ylabel(col)
        ax.grid(True, alpha=0.3)

    fig.suptitle(f"Leituras da balança — {caminho}  ({len(df)} linhas)")
    fig.tight_layout()
    fig.savefig(SAIDA, dpi=120)
    print(f"Gráfico salvo em {SAIDA}")


if __name__ == "__main__":
    grafico_make()
