// ---------- Avisos (substituem os alert) ----------

function avisar(mensagem, tipo = 'ok', duracao = 4000) {
    const aviso = document.createElement('div');
    aviso.className = `aviso ${tipo}`;
    aviso.textContent = mensagem;
    document.getElementById('avisos').appendChild(aviso);
    setTimeout(() => {
        aviso.classList.add('saindo');
        setTimeout(() => aviso.remove(), 300);
    }, duracao);
}

// ---------- Chamadas a API ----------

// Desabilita o botao enquanto a requisicao nao volta, para evitar clique duplo
async function post(url, data = {}, botao = null) {
    if (botao) botao.disabled = true;
    try {
        const resposta = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        const corpo = await resposta.json();
        if (!resposta.ok) {
            avisar(corpo.erro || 'Erro', 'erro', 6000);
        }
        return corpo;
    } catch (erro) {
        avisar('Sem conexão com o cocho', 'erro', 6000);
        return { ok: false };
    } finally {
        if (botao) botao.disabled = false;
    }
}

async function motor(numero, botao) {
    const resposta = await post(`/api/motor/${numero}`, {}, botao);
    if (resposta.ok) avisar(`Motor ${numero} ligado`);
    atualizar();
}

async function parar(numero, botao) {
    const resposta = await post(`/api/motor/${numero}/parar`, {}, botao);
    if (resposta.ok) avisar(`Motor ${numero} parado`);
    atualizar();
}

// Calibracao em tres etapas (pesos definidos no config.py, ex: 0.1, 0.2 e 0.3 kg):
// o mesmo botao inicia a calibracao e registra cada peso; o outro botao cancela
async function calibrar(numero, botao) {
    const resposta = await post(`/api/calibrar/${numero}`, {}, botao);
    if (resposta.concluida) {
        avisar(`Balança ${numero} calibrada (fator ${resposta.fator.toFixed(3)})`);
        if (!resposta.salvo) avisar('O fator não pôde ser salvo no config.py', 'erro', 8000);
    } else if (resposta.mensagem) {
        avisar(resposta.mensagem, 'ok', 8000);
    }
    atualizar();
}

async function cancelarCalibracao(numero, botao) {
    const resposta = await post(`/api/calibrar/${numero}/cancelar`, {}, botao);
    if (resposta.ok) avisar(`Calibração da balança ${numero} cancelada`);
    atualizar();
}

// calibracao: { estado: null | "aguardando_peso" | "lendo", etapa, pesos }
function mostrarCalibracao(numero, calibracao) {
    const { estado = null, etapa = 0, pesos = [] } = calibracao || {};
    const bloco = document.getElementById(`calibracao${numero}`);
    const dica = document.getElementById(`calibracaoDica${numero}`);
    const botao = document.getElementById(`btnCalibrar${numero}`);
    const total = pesos.length;
    const peso = pesos[etapa];
    bloco.dataset.estado = estado || '';
    if (estado === 'lendo') {
        dica.textContent = `Etapa ${etapa + 1} de ${total}: lendo a balança ${numero}… não mexa no peso.`;
        botao.textContent = 'Lendo…';
    } else if (estado === 'aguardando_peso') {
        dica.textContent = `Etapa ${etapa + 1} de ${total}: coloque o peso de ${peso} kg na balança ${numero} e clique em Registrar peso.`;
        botao.textContent = `Registrar peso (${peso} kg)`;
    } else {
        dica.textContent = `Balança ${numero}: clique em Calibrar balança ${numero} e siga as ${total || 3} etapas (${pesos.join(', ')} kg).`;
        botao.textContent = `Calibrar balança ${numero}`;
    }
}

// ---------- Cadastro de ovelhas (RFID) ----------

async function iniciarCadastro(botao) {
    const resposta = await post('/api/cadastro/iniciar', {}, botao);
    if (resposta.ok) atualizar();
}

async function finalizarCadastro(botao) {
    const resposta = await post('/api/cadastro/finalizar', {}, botao);
    if (resposta.ok) {
        document.getElementById('formOvelha').reset();
        atualizar();
    }
}

async function salvarOvelha(evento) {
    evento.preventDefault();
    const formulario = evento.target;
    const nome = document.getElementById('nome').value;
    const peso = document.getElementById('peso').value;
    const tipo = document.getElementById('tipo').value;
    const valor = document.getElementById('valor').value;
    const botao = document.getElementById('btnSalvarOvelha');
    const resposta = await post('/api/cadastro/salvar', { nome, peso, tipo, valor }, botao);
    if (resposta.ok) {
        avisar(`${nome} cadastrada`);
        formulario.reset();
        atualizarTipoRacao();
        atualizar();
    }
}

// Quantidade de Racao: fixa em kg ou porcentagem do peso do animal
function atualizarTipoRacao() {
    const percentual = document.getElementById('tipo').value === 'percentual';
    const peso = parseFloat(document.getElementById('peso').value);
    const valor = parseFloat(document.getElementById('valor').value);
    document.getElementById('rotuloValor').textContent =
        percentual ? 'Quantidade de Ração (% do peso)' : 'Quantidade de Ração (kg)';
    let dica = percentual
        ? 'Porcentagem do peso do animal, ex: 2 = 2% do peso. Acompanha o peso medido na balança.'
        : 'Quantidade de ração por refeição, em kg.';
    if (percentual && peso > 0 && valor > 0) {
        dica += ` Hoje: ${(peso * valor / 100).toFixed(3)} kg.`;
    }
    document.getElementById('dicaRacao').textContent = dica;
}

let estadoCadastroAnterior = null;

// estado: "inativo" | "aguardando_tag" | "tag_nova"
function mostrarCadastro(cadastro) {
    const card = document.getElementById('cardCadastro');
    const texto = document.getElementById('cadastroTexto');
    const estado = cadastro ? cadastro.estado : 'inativo';
    card.dataset.estado = estado;

    const liberarCampos = estado === 'tag_nova';
    for (const id of ['nome', 'peso', 'tipo', 'valor', 'btnSalvarOvelha']) {
        document.getElementById(id).disabled = !liberarCampos;
    }

    if (estado === 'aguardando_tag') {
        texto.textContent = 'Aguardando tag… Aproxime a tag do animal do leitor.';
    } else if (estado === 'tag_nova') {
        texto.innerHTML = 'Tag nova reconhecida. Digite o nome, o peso e a quantidade de ração.<br>';
        const tag = document.createElement('span');
        tag.className = 'cadastro-tag';
        tag.textContent = cadastro.tag;
        texto.appendChild(tag);
    } else {
        texto.textContent = 'Clique em Iniciar cadastro e aproxime a tag do leitor. A alimentação fica pausada durante o cadastro.';
    }

    // leva o cursor para o Nome quando uma tag nova acaba de ser reconhecida
    if (estado === 'tag_nova' && estadoCadastroAnterior !== 'tag_nova') {
        document.getElementById('nome').focus();
    }
    estadoCadastroAnterior = estado;
}

async function reiniciar(botao) {
    if (!confirm('Reiniciar a Raspberry Pi? O cocho fica parado até ela voltar.')) return;
    const resposta = await post('/api/reiniciar', {}, botao);
    if (resposta.ok) avisar('Reiniciando a Raspberry Pi…', 'ok', 10000);
}

// ---------- Atualizacao da tela ----------

// idade: segundos desde a ultima leitura feita pelo loop principal
function mostrarPeso(numero, peso, idade) {
    const card = document.getElementById(`cardPeso${numero}`);
    const valor = document.getElementById(`peso${numero}`);
    const rodape = document.getElementById(`idade${numero}`);

    card.classList.remove('antigo', 'erro');
    if (idade == null) {
        valor.textContent = '—';
        rodape.textContent = 'aguardando leitura';
        return;
    }
    if (peso == null) {
        card.classList.add('erro');
        valor.textContent = 'erro';
        rodape.textContent = 'falha na leitura da balança';
        return;
    }
    valor.textContent = peso.toFixed(3);
    if (idade > 5) {
        card.classList.add('antigo');
        rodape.textContent = `última leitura há ${Math.round(idade)}s`;
    } else {
        rodape.textContent = 'atualizado agora';
    }
}

// ultimaTag: null | { tag, nome, cadastrada, hora, idade } (nome buscado no tag_info.csv)
function mostrarUltimaTag(ultimaTag) {
    const card = document.getElementById('cardTag');
    const nome = document.getElementById('tagNome');
    const id = document.getElementById('tagId');
    const rodape = document.getElementById('tagRodape');

    card.classList.remove('recente', 'desconhecida');
    if (!ultimaTag) {
        nome.textContent = '—';
        id.textContent = '';
        rodape.textContent = 'nenhuma tag lida ainda';
        return;
    }
    if (!ultimaTag.cadastrada) {
        card.classList.add('desconhecida');
        nome.textContent = 'Tag não cadastrada';
    } else {
        nome.textContent = ultimaTag.nome || 'Sem nome no cadastro';
    }
    id.textContent = ultimaTag.tag;
    if (ultimaTag.idade < 10) card.classList.add('recente');
    rodape.textContent = ultimaTag.idade < 5 ? 'lida agora' : `lida às ${ultimaTag.hora}`;
}

// "parado" | "horario (150)" | "antihorario (255)"
function mostrarMotor(numero, estado) {
    const pilula = document.getElementById(`motor${numero}`);
    const ligado = estado && estado !== 'parado';
    pilula.classList.toggle('ligado', Boolean(ligado));
    if (!ligado) {
        pilula.textContent = 'Parado';
        return;
    }
    const texto = estado.replace('antihorario', 'anti-horário').replace('horario', 'horário');
    pilula.textContent = `Girando · ${texto}`;
}

function mostrarConexao(online) {
    const conexao = document.getElementById('conexao');
    conexao.dataset.estado = online ? 'online' : 'offline';
    document.getElementById('conexaoTexto').textContent = online ? 'Online' : 'Sem conexão';
}

async function atualizar() {
    let status;
    try {
        const resposta = await fetch('/api/status');
        status = await resposta.json();
    } catch (erro) {
        mostrarConexao(false);
        return;
    }
    mostrarConexao(true);

    mostrarPeso(1, status.peso1, status.idade_peso1);
    mostrarPeso(2, status.peso2, status.idade_peso2);
    mostrarUltimaTag(status.ultima_tag);
    mostrarMotor(1, status.motor1);
    mostrarMotor(2, status.motor2);
    mostrarCadastro(status.cadastro);
    const calibracao = status.calibracao || {};
    mostrarCalibracao(1, calibracao['1']);
    mostrarCalibracao(2, calibracao['2']);

    document.getElementById('situacao').textContent = status.mensagem;
}

// ---------- Terminal da Raspberry (prints, logging e journal do servico) ----------

const LINHAS_TERMINAL = 500;
let ultimoIdTerminal = 0;

function linhaTerminal({ hora, origem, nivel, texto }) {
    const linha = document.createElement('span');
    linha.className = `linha-${origem} linha-${nivel}`;
    const marcaHora = document.createElement('span');
    marcaHora.className = 'linha-hora';
    marcaHora.textContent = `${hora} `;
    linha.append(marcaHora, `${origem === 'servico' ? '[serviço] ' : ''}${texto}\n`);
    return linha;
}

function filtrarTerminal() {
    const soServico = document.getElementById('terminalSoServico').checked;
    document.getElementById('terminal').classList.toggle('so-servico', soServico);
}

function mostrarServico(servico) {
    const texto = document.getElementById('servico');
    if (!servico || !servico.disponivel) {
        texto.textContent = `Serviço ${servico ? servico.nome : ''} não encontrado (o programa não está rodando pelo systemd?).`;
        return;
    }
    const partes = [`${servico.nome}: ${servico.estado} (${servico.subestado})`];
    if (servico.desde) partes.push(`desde ${servico.desde}`);
    if (servico.pid && servico.pid !== '0') partes.push(`PID ${servico.pid}`);
    if (servico.memoria_mb != null) partes.push(`${servico.memoria_mb} MB`);
    if (servico.reinicios) partes.push(`${servico.reinicios} reinício(s)`);
    texto.textContent = partes.join(' · ');
}

async function atualizarTerminal() {
    let dados;
    try {
        const resposta = await fetch(`/api/terminal?desde=${ultimoIdTerminal}`);
        dados = await resposta.json();
    } catch (erro) {
        return;
    }
    const terminal = document.getElementById('terminal');
    // so rola sozinho se o usuario ja estava vendo o fim (nao atrapalha quem subiu para ler)
    const noFim = terminal.scrollHeight - terminal.scrollTop - terminal.clientHeight < 30;
    if (dados.recomecar) terminal.replaceChildren();
    for (const linha of dados.linhas) terminal.appendChild(linhaTerminal(linha));
    while (terminal.childElementCount > LINHAS_TERMINAL) terminal.firstElementChild.remove();
    if (!terminal.childElementCount) terminal.textContent = 'Nenhuma saída ainda.';
    else if (terminal.firstChild.nodeType === Node.TEXT_NODE) terminal.firstChild.remove();
    if (noFim) terminal.scrollTop = terminal.scrollHeight;
    ultimoIdTerminal = dados.ultimo_id;

    document.getElementById('terminalBalancas').textContent = dados.balancas || '';
    mostrarServico(dados.servico);
}

setInterval(atualizar, 1000);
atualizar();
setInterval(atualizarTerminal, 1000);
atualizarTerminal();
for (const id of ['peso', 'valor']) {
    document.getElementById(id).addEventListener('input', atualizarTipoRacao);
}
