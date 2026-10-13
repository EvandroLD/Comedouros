#!/bin/sh
# Gera maquina_estados.png a partir dos .dot (requer graphviz e imagemagick)
set -e
cd "$(dirname "$0")"
for f in 1_ciclo 2_site 3_botoes; do dot -Tpng -Gdpi=110 "$f.dot" -o "/tmp/$f.png"; done
convert /tmp/2_site.png /tmp/3_botoes.png -background white -gravity center -append /tmp/direita.png
convert /tmp/1_ciclo.png /tmp/direita.png -background white -gravity north +append /tmp/corpo.png
W=$(identify -format %w /tmp/corpo.png)
convert -size ${W}x150 xc:white -font DejaVu-Sans-Bold -pointsize 46 -gravity north -annotate +0+25 "Comedouro automático — máquina de estados" \
  -font DejaVu-Sans -pointsize 22 -annotate +0+95 "4 threads concorrentes · notação: transição [condição] / ação · azul forte = caminho feliz de uma alimentação" /tmp/titulo.png
convert -size ${W}x150 xc:white -font DejaVu-Sans -pointsize 21 -fill "#444444" -gravity northwest \
  -annotate +40+15 "Interações entre threads:\n• USO_COCHO (lock): o ciclo t1 e o cadastro do site t4 usam o mesmo leitor RFID e nunca rodam juntos.   • calibracao_em_andamento(): enquanto o site calibra, o t1 não refaz a tara nem loga pesos.\n• Motores: estado manual (botão t3 ou site t4) sempre sobrepõe o estado normal do t1.\n• relatorio_cocho.csv: gravado pelo t1 em REGISTRANDO e enviado ao Google Sheets pelo t2." /tmp/rodape.png
convert /tmp/titulo.png /tmp/corpo.png /tmp/rodape.png -append -bordercolor white -border 20 +repage -depth 8 ../maquina_estados.png
