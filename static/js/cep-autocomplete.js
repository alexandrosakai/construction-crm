class CEPManager {
    constructor() {
        this.historicoCEPs = JSON.parse(localStorage.getItem('historicoCEPs') || '[]');
        this.setupAutocomplete();
    }

    setupAutocomplete() {
        const cidadeInput = document.getElementById('cidade');
        const estadoInput = document.getElementById('estado');
        
        // Lista de estados
        const estados = [
            {sigla: 'AC', nome: 'Acre'},
            {sigla: 'AL', nome: 'Alagoas'},
            // ... outros estados
        ];

        // Autocomplete para estado
        $(estadoInput).autocomplete({
            source: estados.map(e => e.nome),
            minLength: 1,
            select: (event, ui) => {
                const estado = estados.find(e => e.nome === ui.item.value);
                if (estado) {
                    this.carregarCidades(estado.sigla);
                }
            }
        });

        // Salvar CEP no histórico
        document.getElementById('cep').addEventListener('blur', (e) => {
            const cep = e.target.value.replace(/\D/g, '');
            if (cep.length === 8) {
                this.adicionarAoHistorico({
                    cep,
                    logradouro: document.getElementById('logradouro').value,
                    cidade: cidadeInput.value,
                    estado: estadoInput.value
                });
            }
        });
    }

    adicionarAoHistorico(dados) {
        this.historicoCEPs = [dados, ...this.historicoCEPs.slice(0, 9)];
        localStorage.setItem('historicoCEPs', JSON.stringify(this.historicoCEPs));
    }
} 