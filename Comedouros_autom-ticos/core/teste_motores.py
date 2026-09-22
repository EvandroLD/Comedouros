import motor as mt
from config import *
import time
mt.setup_todos_os_motores()
mt._definir_estado_normal(2,'horario',255)
time.sleep(5)
mt._definir_estado_normal(2,'antihorario', 255)
time.sleep(5)
mt._definir_estado_normal(2,'parado', 0)

