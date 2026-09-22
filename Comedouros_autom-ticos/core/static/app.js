async function post(url, data = {}) {
    const resposta = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    const corpo = await resposta.json();
    if (!resposta.ok) {
        alert(corpo.erro || 'Erro');
    }
    return corpo;
}

function motor(numero) {
    post(`/api/motor/${numero}`);
}

function parar(numero) {
    post(`/api/motor/${numero}/parar`);
}

async function calibrar2() {
    const peso = Number(document.getElementById('pesoCalibracao').value);
    if (!peso) {
        alert('Informe o peso conhecido');
        return;
    }
    const resposta = await post('/api/calibrar/2', { peso });
    if (resposta.mensagem) {
        alert(resposta.mensagem);
    }
}

function cadastrar() {
    const tagId = document.getElementById('tag').value;
    const nome = document.getElementById('nome').value;
    const peso = document.getElementById('peso').value;
    post('/api/ovelha', { tag_id: tagId, nome, peso }).then((resposta) => {
        if (resposta.ok) {
            alert('Ovelha cadastrada');
        }
    });
}

function reiniciar() {
    if (confirm('Reiniciar a Raspberry Pi?')) {
        post('/api/reiniciar');
    }
}

async function atualizar() {
    const resposta = await fetch('/api/status');
    const status = await resposta.json();

    document.getElementById('pesos').textContent =
        `Balança 1: ${status.peso1 ?? 'erro'} kg | Balança 2: ${status.peso2 ?? 'erro'} kg`;

    document.getElementById('situacao').textContent =
        `${status.mensagem}\nMotor 1: ${status.motor1}\nMotor 2: ${status.motor2}`;

    document.getElementById('logs').textContent = status.logs.join('\n');
}

setInterval(atualizar, 1000);
atualizar();
