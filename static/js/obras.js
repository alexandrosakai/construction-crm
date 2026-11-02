class GerenciadorObras {
    constructor() {
        this.prefixo = 'OBR';
        this.padding = 6;
        this.modalPesquisa = new bootstrap.Modal(document.getElementById('modalPesquisaObra'));
        this.initEventListeners();
    }

    initEventListeners() {
        // Campo número da obra
        const numeroObra = document.getElementById('numeroObra');
        numeroObra.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.processarNumeroObra(numeroObra.value);
            }
        });

        // Botão de pesquisa
        document.getElementById('pesquisarObra').addEventListener('click', () => {
            this.abrirPesquisa();
        });

        // Pesquisa no modal
        document.getElementById('pesquisaObraModal').addEventListener('input', (e) => {
            this.filtrarObras(e.target.value);
        });

        // Nova obra pelo modal
        document.getElementById('novaObraModal').addEventListener('click', () => {
            this.criarNovaObra();
        });
    }

    async processarNumeroObra(numero) {
        if (!numero) {
            await this.criarNovaObra();
            return;
        }

        const obra = await this.buscarObra(numero);
        if (obra) {
            this.carregarObra(obra);
        } else {
            this.mostrarFeedback('Obra não encontrada. Pressione Enter para criar nova obra.', 'warning');
        }
    }

    async criarNovaObra() {
        const proximoNumero = await this.gerarProximoNumero();
        const numeroFormatado = this.formatarNumero(proximoNumero);
        
        document.getElementById('numeroObra').value = numeroFormatado;
        this.mostrarFeedback(`Nova obra criada com número ${numeroFormatado}`, 'success');
        this.modalPesquisa.hide();
        
        // Limpar formulário mantendo o responsável
        const responsavel = document.getElementById('responsavelCadastro').value;
        document.getElementById('obraForm').reset();
        document.getElementById('numeroObra').value = numeroFormatado;
        document.getElementById('responsavelCadastro').value = responsavel;
    }

    async gerarProximoNumero() {
        const obras = await this.getObras();
        const numeros = obras.map(obra => parseInt(obra.numero.replace(this.prefixo, '')));
        const maximo = Math.max(0, ...numeros);
        return maximo + 1;
    }

    formatarNumero(numero) {
        return `${this.prefixo}${numero.toString().padStart(this.padding, '0')}`;
    }

    async buscarObra(numero) {
        const obras = await this.getObras();
        return obras.find(obra => obra.numero === numero);
    }

    async getObras() {
        // Buscar obras do localStorage ou API
        return JSON.parse(localStorage.getItem('obras') || '[]');
    }

    async filtrarObras(termo) {
        const obras = await this.getObras();
        const filtradas = obras.filter(obra => 
            obra.numero.includes(termo) || 
            obra.cliente?.toLowerCase().includes(termo.toLowerCase())
        );

        this.renderizarObras(filtradas);
    }

    renderizarObras(obras) {
        const tbody = document.getElementById('listaObras');
        tbody.innerHTML = obras.map(obra => `
            <tr>
                <td>${obra.numero}</td>
                <td>${obra.cliente || '-'}</td>
                <td>${obra.data || '-'}</td>
                <td>
                    <span class="badge bg-${this.getStatusColor(obra.status)}">
                        ${obra.status || 'Novo'}
                    </span>
                </td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="gerenciadorObras.carregarObra('${obra.numero}')">
                        <i class="fas fa-edit"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    }

    getStatusColor(status) {
        const cores = {
            'novo': 'primary',
            'em_andamento': 'warning',
            'concluido': 'success',
            'cancelado': 'danger'
        };
        return cores[status] || 'secondary';
    }

    carregarObra(obra) {
        // Implementar carregamento dos dados da obra
        document.getElementById('numeroObra').value = obra.numero;
        this.mostrarFeedback(`Obra ${obra.numero} carregada`, 'success');
        this.modalPesquisa.hide();
    }

    mostrarFeedback(mensagem, tipo) {
        const feedback = document.getElementById('obraFeedback');
        feedback.textContent = mensagem;
        feedback.className = `text-${tipo}`;
        
        // Limpar após 3 segundos
        setTimeout(() => {
            feedback.textContent = '';
            feedback.className = 'text-muted';
        }, 3000);
    }

    abrirPesquisa() {
        this.filtrarObras('');
        this.modalPesquisa.show();
    }
}

// Inicializar gerenciador
const gerenciadorObras = new GerenciadorObras(); 