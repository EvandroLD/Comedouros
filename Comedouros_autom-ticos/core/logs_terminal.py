"""Copia para o site tudo o que aparece no terminal da Raspberry.

Duas fontes alimentam o mesmo buffer:
  - stdout/stderr deste processo (print, logging, tracebacks), capturados aqui mesmo;
  - o journal do servico do systemd (SERVICO_SISTEMA): mensagens do proprio systemd
    (iniciado, parado, travou, reiniciou) e a saida de execucoes anteriores do programa,
    por exemplo o traceback que derrubou o servico antes do reinicio.
As linhas do journal que vieram deste processo sao ignoradas, porque ja foram capturadas.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque

from config import SERVICO_SISTEMA

LINHAS_MAXIMAS = 500
#Linha impressa a cada 0,5 s pelo loop principal: guardada a parte (so a ultima) para
#nao empurrar para fora do buffer as mensagens que importam.
PREFIXO_BALANCAS = "[BALANCAS]"
INTERVALO_STATUS_SERVICO = 10

_LOCK = threading.Lock()
_LINHAS = deque(maxlen=LINHAS_MAXIMAS)
_PROXIMO_ID = 1
_ULTIMA_BALANCA = None
_STATUS_SERVICO = {"nome": SERVICO_SISTEMA, "disponivel": False}
_INSTALADO = False
_LEITURA_SERVICO_INICIADA = False

#Registro de cada requisicao feita ao site pelo Flask (ex: o GET /api/status de cada segundo).
#Continua aparecendo no terminal e no journal, so nao vai para o site.
_ACESSO_FLASK = re.compile(r'werkzeug.*"(GET|POST|PUT|DELETE|HEAD|OPTIONS) \S+ HTTP/[\d.]+" \d{3}')

_ERRO = re.compile(r"\b(ERROR|CRITICAL|Traceback|Exception|Erro|ERRO|Falha|failed|Failed)\b")
_ALERTA = re.compile(r"\b(WARNING|Aviso|Atenção|Atencao)\b")


def _nivel(texto, prioridade=None):
    #prioridade do journal: 0-3 erro, 4 aviso
    if prioridade is not None and prioridade <= 3:
        return "erro"
    if prioridade == 4:
        return "alerta"
    if _ERRO.search(texto):
        return "erro"
    if _ALERTA.search(texto):
        return "alerta"
    return "info"


def adicionar_linha(texto, origem="terminal", hora=None, prioridade=None):
    global _PROXIMO_ID, _ULTIMA_BALANCA
    texto = texto.rstrip()
    if not texto or _ACESSO_FLASK.search(texto):
        return
    hora = hora or time.strftime("%d/%m %H:%M:%S")
    with _LOCK:
        if texto.startswith(PREFIXO_BALANCAS):
            _ULTIMA_BALANCA = f"{hora} {texto}"
            return
        _LINHAS.append({
            "id": _PROXIMO_ID,
            "hora": hora,
            "origem": origem,      #terminal | servico
            "nivel": _nivel(texto, prioridade),
            "texto": texto,
        })
        _PROXIMO_ID += 1


class _Espelho:
    """Envolve sys.stdout/sys.stderr: escreve no terminal normalmente e copia cada linha completa."""

    def __init__(self, original):
        self._original = original
        self._pendente = ""
        self._lock = threading.Lock()

    def write(self, texto):
        resultado = self._original.write(texto)
        try:
            with self._lock:
                self._pendente += texto
                *linhas, self._pendente = self._pendente.split("\n")
            for linha in linhas:
                adicionar_linha(linha.replace("\r", ""))
        except Exception:
            pass  #o espelho nunca pode derrubar um print
        return resultado

    def flush(self):
        self._original.flush()

    def __getattr__(self, nome):
        return getattr(self._original, nome)


def instalar():
    """Passa a copiar stdout e stderr para o buffer. Chamar antes do logging.basicConfig."""
    global _INSTALADO
    if _INSTALADO:
        return
    _INSTALADO = True
    for nome in ("stdout", "stderr"):
        stream = getattr(sys, nome)
        try:
            #rodando como servico a saida nao e um terminal e o Python segura os prints
            #em blocos de 8 KB; assim cada linha chega na hora no journal e no site
            stream.reconfigure(line_buffering=True)
        except Exception:
            pass
        setattr(sys, nome, _Espelho(stream))


# ---------- Servico do systemd ----------

def _hora_journal(entrada):
    try:
        segundos = int(entrada["__REALTIME_TIMESTAMP"]) / 1_000_000
        return time.strftime("%d/%m %H:%M:%S", time.localtime(segundos))
    except (KeyError, ValueError):
        return None


def _texto_journal(entrada):
    mensagem = entrada.get("MESSAGE", "")
    if isinstance(mensagem, list):  #mensagem que nao e UTF-8 vem como lista de bytes
        mensagem = bytes(mensagem).decode("utf-8", errors="replace")
    origem = entrada.get("SYSLOG_IDENTIFIER") or ""
    return f"{origem}: {mensagem}" if origem else str(mensagem)


def _seguir_journal():
    meu_pid = str(os.getpid())
    avisos = set()  #avisos do journalctl repetem a cada nova tentativa: mostra cada um uma vez so
    comando = ["journalctl", "-u", SERVICO_SISTEMA, "-f", "-n", "100", "-o", "json", "--no-pager"]
    while True:
        try:
            processo = subprocess.Popen(
                comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
        except Exception as erro:
            adicionar_linha(f"Não foi possível ler o journal do {SERVICO_SISTEMA}: {erro}", "servico", prioridade=3)
            return
        for linha in processo.stdout:
            try:
                entrada = json.loads(linha)
            except ValueError:
                #avisos do proprio journalctl, ex: falta de permissao para ler o journal
                if linha not in avisos:
                    avisos.add(linha)
                    adicionar_linha(f"journalctl: {linha}", "servico", prioridade=4)
                continue
            if entrada.get("_PID") == meu_pid:
                continue
            prioridade = entrada.get("PRIORITY")
            adicionar_linha(
                _texto_journal(entrada), "servico", _hora_journal(entrada),
                int(prioridade) if str(prioridade).isdigit() else None,
            )
        processo.wait()
        aviso = f"Leitura do journal encerrada (código {processo.returncode}); tentando de novo a cada 30 s."
        if aviso not in avisos:
            avisos.add(aviso)
            adicionar_linha(aviso, "servico", prioridade=4)
        time.sleep(30)
        comando[comando.index("-n") + 1] = "0"  #nao repete as linhas antigas


def _atualizar_status_servico():
    propriedades = ["LoadState", "ActiveState", "SubState", "ActiveEnterTimestamp", "MainPID", "NRestarts", "MemoryCurrent", "User"]
    while True:
        try:
            saida = subprocess.run(
                ["systemctl", "show", SERVICO_SISTEMA, "-p", ",".join(propriedades)],
                capture_output=True, text=True, timeout=5,
            ).stdout
            valores = dict(linha.split("=", 1) for linha in saida.splitlines() if "=" in linha)
            memoria = valores.get("MemoryCurrent", "")
            status = {
                "nome": SERVICO_SISTEMA,
                "disponivel": valores.get("LoadState") == "loaded",
                "estado": valores.get("ActiveState"),
                "subestado": valores.get("SubState"),
                "desde": valores.get("ActiveEnterTimestamp"),
                "pid": valores.get("MainPID"),
                "reinicios": valores.get("NRestarts"),
                "memoria_mb": round(int(memoria) / 1024 / 1024, 1) if memoria.isdigit() else None,
                "usuario": valores.get("User") or "root",
                "este_processo": valores.get("MainPID") == str(os.getpid()),
            }
        except Exception as erro:
            status = {"nome": SERVICO_SISTEMA, "disponivel": False, "erro": str(erro)}
        with _LOCK:
            _STATUS_SERVICO.clear()
            _STATUS_SERVICO.update(status)
        time.sleep(INTERVALO_STATUS_SERVICO)


def iniciar_leitura_servico():
    """Sobe as threads que leem o journal e o estado do servico (so na Raspberry, com systemd)."""
    global _LEITURA_SERVICO_INICIADA
    if _LEITURA_SERVICO_INICIADA:
        return
    _LEITURA_SERVICO_INICIADA = True
    if shutil.which("journalctl"):
        threading.Thread(target=_seguir_journal, daemon=True).start()
    if shutil.which("systemctl"):
        threading.Thread(target=_atualizar_status_servico, daemon=True).start()


def linhas_desde(ultimo_id=0):
    """Linhas com id maior que `ultimo_id`, a ultima leitura das balancas e o estado do servico."""
    with _LOCK:
        primeiro_id = _LINHAS[0]["id"] if _LINHAS else _PROXIMO_ID
        #o site guardava um id que ja saiu do buffer, ou o programa reiniciou: manda tudo de novo
        recomecar = ultimo_id > _PROXIMO_ID - 1 or ultimo_id < primeiro_id - 1
        if recomecar:
            ultimo_id = 0
        return {
            "linhas": [linha for linha in _LINHAS if linha["id"] > ultimo_id],
            "ultimo_id": _PROXIMO_ID - 1,
            "recomecar": recomecar,
            "balancas": _ULTIMA_BALANCA,
            "servico": dict(_STATUS_SERVICO),
        }
