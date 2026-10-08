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

// Calibracao em dois passos, igual nas duas balancas:
// 1o clique zera a balanca; 2o clique (com o peso conhecido em cima) calcula o fator
async function calibrar(numero, botao) {
    const peso = Number(document.getElementById(`pesoCalibracao${numero}`).value);
    if (!peso) {
        avisar(`Informe o peso conhecido da balança ${numero}`, 'erro');
        return;
    }
    const resposta = await post(`/api/calibrar/${numero}`, { peso }, botao);
    if (resposta.mensagem) {
        avisar(resposta.mensagem, 'ok', 8000);
    } else if (resposta.ok) {
        avisar(`Balança ${numero} calibrada (fator ${resposta.fator.toFixed(3)})`);
    }
    atualizar();
}

async function cancelarCalibracao(numero, botao) {
    const resposta = await post(`/api/calibrar/${numero}/cancelar`, {}, botao);
    if (resposta.ok) avisar(`Calibração da balança ${numero} cancelada`);
    atualizar();
}

// estado: null | "zerando" | "aguardando_peso"
function mostrarCalibracao(numero, estado) {
    const bloco = document.getElementById(`calibracao${numero}`);
    const dica = document.getElementById(`calibracaoDica${numero}`);
    const botao = document.getElementById(`btnCalibrar${numero}`);
    bloco.dataset.estado = estado || '';
    if (estado === 'zerando') {
        dica.textContent = `Zerando a balança ${numero}… mantenha sem peso.`;
        botao.textContent = 'Zerando…';
    } else if (estado === 'aguardando_peso') {
        dica.textContent = `Coloque o peso conhecido na balança ${numero} e clique em Concluir.`;
        botao.textContent = 'Concluir calibração';
    } else {
        dica.textContent = `Balança ${numero}: clique uma vez sem peso, depois coloque o peso conhecido e clique de novo.`;
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
    const valor = document.getElementById('valor').value;
    const botao = document.getElementById('btnSalvarOvelha');
    const resposta = await post('/api/cadastro/salvar', { nome, peso, valor }, botao);
    if (resposta.ok) {
        avisar(`${nome} cadastrada`);
        formulario.reset();
        atualizar();
    }
}

let estadoCadastroAnterior = null;

// estado: "inativo" | "aguardando_tag" | "tag_nova"
function mostrarCadastro(cadastro) {
    const card = document.getElementById('cardCadastro');
    const texto = document.getElementById('cadastroTexto');
    const estado = cadastro ? cadastro.estado : 'inativo';
    card.dataset.estado = estado;

    const liberarCampos = estado === 'tag_nova';
    for (const id of ['nome', 'peso', 'valor', 'btnSalvarOvelha']) {
        document.getElementById(id).disabled = !liberarCampos;
    }

    if (estado === 'aguardando_tag') {
        texto.textContent = 'Aguardando tag… Aproxime a tag do animal do leitor.';
    } else if (estado === 'tag_nova') {
        texto.innerHTML = 'Tag nova reconhecida. Digite o nome, o peso e o valor.<br>';
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
    mostrarMotor(1, status.motor1);
    mostrarMotor(2, status.motor2);
    mostrarCadastro(status.cadastro);
    const calibracao = status.calibracao || {};
    mostrarCalibracao(1, calibracao['1']);
    mostrarCalibracao(2, calibracao['2']);

    document.getElementById('situacao').textContent = status.mensagem;
    document.getElementById('logs').textContent = status.logs.length
        ? status.logs.join('\n')
        : 'Nenhum evento ainda.';
}

setInterval(atualizar, 1000);
atualizar();