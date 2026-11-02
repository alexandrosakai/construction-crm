// Adicionar suporte a touch events
function addTouchSupport() {
    // Converter hover events para touch
    document.querySelectorAll('.hover-effect').forEach(element => {
        element.addEventListener('touchstart', function(e) {
            e.preventDefault();
            this.classList.add('hover');
        });

        element.addEventListener('touchend', function() {
            this.classList.remove('hover');
        });
    });

    // Melhorar interação com mapas em touch
    if (window.google && window.google.maps) {
        const map = document.getElementById('map');
        if (map) {
            map.addEventListener('touchstart', function(e) {
                e.stopPropagation();
            }, { passive: true });
        }
    }
}

// Ajustar layout baseado no tamanho da tela
function adjustLayout() {
    const isMobile = window.innerWidth < 768;
    const isTablet = window.innerWidth >= 768 && window.innerWidth < 1024;

    // Ajustar tamanho de elementos baseado no dispositivo
    document.querySelectorAll('.card').forEach(card => {
        if (isMobile) {
            card.classList.add('mobile-view');
        } else {
            card.classList.remove('mobile-view');
        }
    });

    // Ajustar comportamento de modais
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        if (isMobile) {
            modal.classList.add('modal-fullscreen');
        } else {
            modal.classList.remove('modal-fullscreen');
        }
    });
}

// Inicializar responsividade
document.addEventListener('DOMContentLoaded', function() {
    addTouchSupport();
    adjustLayout();

    // Reajustar layout quando a tela for redimensionada
    window.addEventListener('resize', adjustLayout);
});

// Função para buscar CEP
async function buscarCEP(cep) {
    if (cep.length !== 8) {
        alert('CEP inválido');
        return;
    }

    try {
        // Mostrar loading no botão
        const btnBuscar = document.getElementById('buscarCep');
        const btnText = btnBuscar.innerHTML;
        btnBuscar.disabled = true;
        btnBuscar.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

        // Buscar CEP na API ViaCEP
        const response = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
        const data = await response.json();

        if (data.erro) {
            throw new Error('CEP não encontrado');
        }

        // Preencher campos
        document.getElementById('logradouro').value = data.logradouro;
        document.getElementById('bairro').value = data.bairro;
        document.getElementById('cidade').value = data.localidade;
        document.getElementById('estado').value = data.uf;

        // Atualizar mapa com o endereço completo
        const enderecoCompleto = `${data.logradouro}, ${data.bairro}, ${data.localidade}, ${data.uf}`;
        atualizarMapa(enderecoCompleto);

    } catch (error) {
        console.error('Erro ao buscar CEP:', error);
        alert('Erro ao buscar CEP. Verifique se o CEP está correto.');
    } finally {
        // Restaurar botão
        const btnBuscar = document.getElementById('buscarCep');
        btnBuscar.disabled = false;
        btnBuscar.innerHTML = 'Buscar';
    }
}

// Variáveis globais para o mapa
let map, marker, geocoder;

// Função para inicializar o mapa
function initMap() {
    try {
        // Coordenadas iniciais (Brasil)
        const defaultLocation = { lat: -15.7801, lng: -47.9292 };
        
        // Criar o mapa
        map = new google.maps.Map(document.getElementById('map'), {
            zoom: 4,
            center: defaultLocation,
            mapTypeId: google.maps.MapTypeId.ROADMAP,
            mapTypeControl: true,
            streetViewControl: true,
            fullscreenControl: true,
            zoomControl: true
        });

        // Inicializar geocoder
        geocoder = new google.maps.Geocoder();

        // Criar marcador
        marker = new google.maps.Marker({
            map: map,
            position: defaultLocation,
            draggable: false,
            animation: google.maps.Animation.DROP
        });

        // Adicionar evento para atualizar mapa quando CEP for buscado
        document.getElementById('buscarCep').addEventListener('click', function() {
            setTimeout(function() {
                const logradouro = document.getElementById('logradouro').value;
                const numero = document.getElementById('numero').value;
                const bairro = document.getElementById('bairro').value;
                const cidade = document.getElementById('cidade').value;
                const estado = document.getElementById('estado').value;

                if (logradouro && cidade) {
                    const enderecoCompleto = `${logradouro}, ${numero || 'S/N'}, ${bairro}, ${cidade}, ${estado}, Brasil`;
                    atualizarMapa(enderecoCompleto);
                }
            }, 1000);
        });

    } catch (error) {
        console.error('Erro ao inicializar mapa:', error);
    }
}

// Função para atualizar o mapa com um endereço
function atualizarMapa(endereco) {
    if (!geocoder || !map || !marker) {
        console.error('Componentes do mapa não inicializados');
        return;
    }

    try {
        geocoder.geocode({ address: endereco }, function(results, status) {
            if (status === 'OK' && results[0]) {
                const location = results[0].geometry.location;
                
                // Centralizar mapa
                map.setCenter(location);
                map.setZoom(16);
                
                // Atualizar marcador
                marker.setPosition(location);
                
                // Criar e abrir InfoWindow
                const infowindow = new google.maps.InfoWindow({
                    content: `
                        <div style="padding: 10px;">
                            <strong>Endereço:</strong><br>
                            ${results[0].formatted_address}
                        </div>
                    `
                });

                // Fechar InfoWindow anterior se existir
                if (marker.infowindow) {
                    marker.infowindow.close();
                }
                
                // Guardar referência da InfoWindow atual
                marker.infowindow = infowindow;
                
                // Abrir InfoWindow
                infowindow.open(map, marker);
            } else {
                console.error('Erro ao geocodificar endereço:', status);
            }
        });
    } catch (error) {
        console.error('Erro ao atualizar mapa:', error);
    }
}

// Função para atualizar mapa após preenchimento do endereço
function atualizarMapaPorEndereco() {
    const logradouro = document.getElementById('logradouro').value;
    const numero = document.getElementById('numero').value;
    const bairro = document.getElementById('bairro').value;
    const cidade = document.getElementById('cidade').value;
    const estado = document.getElementById('estado').value;

    if (logradouro && cidade) {
        const enderecoCompleto = `${logradouro}, ${numero || 'S/N'}, ${bairro}, ${cidade}, ${estado}`;
        atualizarMapa(enderecoCompleto);
    }
}

// Adicionar eventos quando o documento estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    // Evento para buscar CEP
    document.getElementById('buscarCep').addEventListener('click', function() {
        const logradouro = document.getElementById('logradouro').value.trim();
        const cidade = document.getElementById('cidade').value.trim();
        const estado = document.getElementById('estado').value.trim();

        if (logradouro && cidade && estado) {
            buscarCEPsPorLogradouro(logradouro, cidade, estado);
        } else {
            const cep = document.getElementById('cep').value.replace(/\D/g, '');
            if (cep.length === 8) {
                buscarCEP(cep);
            } else {
                alert('Preencha o logradouro, cidade e estado para buscar o CEP ou informe um CEP válido');
            }
        }
    });

    // Máscara para o CEP
    const cepInput = document.getElementById('cep');
    cepInput.addEventListener('input', function(e) {
        let value = e.target.value.replace(/\D/g, '');
        if (value.length > 8) value = value.slice(0, 8);
        if (value.length > 5) {
            value = value.slice(0, 5) + '-' + value.slice(5);
        }
        e.target.value = value;
    });

    // Buscar CEP ao pressionar Enter
    cepInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            buscarCEP();
        }
    });

    // Eventos para atualização do mapa
    document.getElementById('numero').addEventListener('blur', atualizarMapaPorEndereco);
    document.getElementById('buscarCep').addEventListener('click', function() {
        setTimeout(atualizarMapaPorEndereco, 1000); // Aguardar preenchimento dos campos
    });

    // Atualizar mapa quando número for preenchido
    document.getElementById('numero').addEventListener('blur', function() {
        const logradouro = document.getElementById('logradouro').value;
        const numero = this.value;
        const bairro = document.getElementById('bairro').value;
        const cidade = document.getElementById('cidade').value;
        const estado = document.getElementById('estado').value;

        if (logradouro && cidade) {
            const enderecoCompleto = `${logradouro}, ${numero || 'S/N'}, ${bairro}, ${cidade}, ${estado}`;
            window.atualizarMapa(enderecoCompleto);
        }
    });
});

// Funções de importação e exportação
function inicializarImportExport() {
    const btnExportar = document.getElementById('btnExportar');
    const btnImportar = document.getElementById('btnImportar');
    const inputImportar = document.getElementById('inputImportar');

    // Função para exportar dados
    async function exportarDados() {
        try {
            // Mostrar loading
            btnExportar.disabled = true;
            btnExportar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Exportando...';

            // Obter dados do localStorage
            const obras = JSON.parse(localStorage.getItem('obras') || '{}');
            const favoritos = JSON.parse(localStorage.getItem('obrasFavoritas') || '[]');

            // Preparar dados para exportação
            const dadosExportar = Object.entries(obras).map(([numeroObra, obra]) => ({
                'Número da Obra': numeroObra,
                'Nome': obra.nome || '',
                'Sobrenome': obra.sobrenome || '',
                'CPF': obra.cpf || '',
                'Telefone': obra.telefone || '',
                'Email': obra.email || '',
                'CEP': obra.cep || '',
                'Logradouro': obra.logradouro || '',
                'Número': obra.numero || '',
                'Bairro': obra.bairro || '',
                'Cidade': obra.cidade || '',
                'Estado': obra.estado || '',
                'Tipo de Obra': obra.tipoObra || '',
                'Padrão da Obra': obra.padraoObra || '',
                'Potencial': obra.potencialObra || '',
                'Metragem': obra.metragem || '',
                'Data de Início': obra.dataInicio || '',
                'Data de Término': obra.dataTermino || '',
                'Favorito': favoritos.includes(numeroObra) ? 'Sim' : 'Não'
            }));

            // Criar workbook
            const wb = XLSX.utils.book_new();
            const ws = XLSX.utils.json_to_sheet(dadosExportar);

            // Adicionar worksheet ao workbook
            XLSX.utils.book_append_sheet(wb, ws, "Obras");

            // Gerar arquivo
            const dataAtual = new Date().toISOString().split('T')[0];
            XLSX.writeFile(wb, `obras_exemplo_${dataAtual}.xlsx`);

            alert('Dados exportados com sucesso!');
        } catch (error) {
            console.error('Erro ao exportar:', error);
            alert('Erro ao exportar dados. Tente novamente.');
        } finally {
            // Restaurar botão
            btnExportar.disabled = false;
            btnExportar.innerHTML = '<i class="fas fa-file-export"></i> Exportar Dados (XLSX)';
        }
    }

    // Função para importar dados
    async function importarDados(file) {
        try {
            // Mostrar loading
            btnImportar.disabled = true;
            btnImportar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Importando...';

            const reader = new FileReader();
            reader.onload = async function(e) {
                try {
                    const data = new Uint8Array(e.target.result);
                    const workbook = XLSX.read(data, { type: 'array' });
                    
                    // Pegar primeira planilha
                    const worksheet = workbook.Sheets[workbook.SheetNames[0]];
                    const jsonData = XLSX.utils.sheet_to_json(worksheet);

                    // Validar dados
                    if (!jsonData.length) {
                        throw new Error('Arquivo vazio ou inválido');
                    }

                    // Converter para formato do sistema
                    const obras = {};
                    const favoritos = [];

                    jsonData.forEach(row => {
                        const numeroObra = row['Número da Obra']?.toString();
                        if (!numeroObra) return;

                        obras[numeroObra] = {
                            nome: row['Nome'] || '',
                            sobrenome: row['Sobrenome'] || '',
                            cpf: row['CPF'] || '',
                            telefone: row['Telefone'] || '',
                            email: row['Email'] || '',
                            cep: row['CEP'] || '',
                            logradouro: row['Logradouro'] || '',
                            numero: row['Número'] || '',
                            bairro: row['Bairro'] || '',
                            cidade: row['Cidade'] || '',
                            estado: row['Estado'] || '',
                            tipoObra: row['Tipo de Obra'] || '',
                            padraoObra: row['Padrão da Obra'] || '',
                            potencialObra: row['Potencial'] || '',
                            metragem: row['Metragem'] || '',
                            dataInicio: row['Data de Início'] || '',
                            dataTermino: row['Data de Término'] || ''
                        };

                        if (row['Favorito']?.toLowerCase() === 'sim') {
                            favoritos.push(numeroObra);
                        }
                    });

                    // Salvar dados
                    localStorage.setItem('obras', JSON.stringify(obras));
                    localStorage.setItem('obrasFavoritas', JSON.stringify(favoritos));

                    alert('Dados importados com sucesso!');
                    setTimeout(() => window.location.reload(), 1000);
                } catch (error) {
                    console.error('Erro ao processar arquivo:', error);
                    alert('Erro ao processar arquivo. Verifique se o formato está correto.');
                }
            };

            reader.readAsArrayBuffer(file);
        } catch (error) {
            console.error('Erro ao importar:', error);
            alert('Erro ao importar dados. Tente novamente.');
        } finally {
            // Restaurar botão
            btnImportar.disabled = false;
            btnImportar.innerHTML = '<i class="fas fa-file-import"></i> Importar Dados (XLSX)';
        }
    }

    // Eventos
    btnExportar.addEventListener('click', exportarDados);
    
    btnImportar.addEventListener('click', () => {
        inputImportar.click();
    });

    inputImportar.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            const file = e.target.files[0];
            if (confirm('Isso irá substituir todos os dados existentes. Deseja continuar?')) {
                importarDados(file);
            }
            e.target.value = ''; // Limpar input
        }
    });
}

// Inicializar importação/exportação
document.addEventListener('DOMContentLoaded', function() {
    inicializarImportExport();
});

// Expor função globalmente para callback do Google Maps
window.initMap = initMap;
window.atualizarMapa = atualizarMapa;

// Funções de relatório
function inicializarRelatorios() {
    const btnGerarRelatorio = document.getElementById('gerarRelatorio');
    const btnLimparFiltros = document.getElementById('limparFiltros');

    btnGerarRelatorio.addEventListener('click', function() {
        const filtros = {
            dataInicio: document.getElementById('filtroDataInicio').value,
            dataFim: document.getElementById('filtroDataFim').value,
            incluirProfissionais: document.getElementById('checkProfissionais').checked,
            incluirEtapas: document.getElementById('checkEtapas').checked,
            incluirVisitas: document.getElementById('checkVisitas').checked,
            incluirVendedores: document.getElementById('checkVendedores').checked,
            incluirFornecedores: document.getElementById('checkFornecedores').checked,
            incluirFotos: document.getElementById('checkFotos').checked,
            formato: document.getElementById('formatoRelatorio').value
        };

        if (!filtros.dataInicio || !filtros.dataFim) {
            alert('Por favor, selecione o período do relatório');
            return;
        }

        if (!Object.values(filtros).slice(2, 8).some(v => v)) {
            alert('Selecione pelo menos um tipo de dado para incluir no relatório');
            return;
        }

        gerarRelatorio(filtros);
    });

    btnLimparFiltros.addEventListener('click', function() {
        document.getElementById('filtroDataInicio').value = '';
        document.getElementById('filtroDataFim').value = '';
        document.querySelectorAll('.form-check-input').forEach(checkbox => {
            checkbox.checked = false;
        });
        document.getElementById('formatoRelatorio').value = 'pdf';
    });
}

async function gerarRelatorio(filtros) {
    try {
        const btnGerar = document.getElementById('gerarRelatorio');
        btnGerar.disabled = true;
        btnGerar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Gerando...';

        // Buscar obras do período selecionado
        const obras = JSON.parse(localStorage.getItem('obras') || '{}');
        const obrasArray = Object.entries(obras).filter(([_, obra]) => {
            const dataObra = new Date(obra.dataInicio);
            return dataObra >= new Date(filtros.dataInicio) && 
                   dataObra <= new Date(filtros.dataFim);
        });

        // Preparar dados do relatório
        const dadosRelatorio = obrasArray.map(([numeroObra, obra]) => {
            const dados = {};

            // Dados Básicos
            if (document.getElementById('checkNumeroObra').checked) {
                dados['Número da Obra'] = numeroObra;
            }
            if (document.getElementById('checkDatas').checked) {
                dados['Data de Início'] = obra.dataInicio;
                dados['Data de Término'] = obra.dataTermino;
            }
            if (document.getElementById('checkCliente').checked) {
                dados['Cliente'] = `${obra.nome} ${obra.sobrenome}`;
                dados['Telefone'] = obra.telefone;
                dados['Email'] = obra.email;
            }
            if (document.getElementById('checkEndereco').checked) {
                dados['Endereço'] = `${obra.logradouro}, ${obra.numero}`;
                dados['Bairro'] = obra.bairro;
                dados['Cidade'] = obra.cidade;
                dados['Estado'] = obra.estado;
                dados['CEP'] = obra.cep;
            }
            if (document.getElementById('checkMetragem').checked) {
                dados['Metragem'] = obra.metragem;
            }
            if (document.getElementById('checkStatus').checked) {
                dados['Status'] = obra.status;
            }

            // Profissionais
            if (obra.profissionais && obra.profissionais.length > 0) {
                const dadosProfissionais = obra.profissionais.map(p => {
                    const partes = [];
                    if (document.getElementById('checkProfissionaisNome').checked) {
                        partes.push(p.nome);
                    }
                    if (document.getElementById('checkProfissionaisEspecialidade').checked) {
                        partes.push(`(${p.especialidade})`);
                    }
                    if (document.getElementById('checkProfissionaisTelefone').checked) {
                        partes.push(p.telefone);
                    }
                    if (document.getElementById('checkProfissionaisAvaliacao').checked) {
                        partes.push(`Avaliação: ${p.avaliacao || 'N/A'}`);
                    }
                    return partes.join(' - ');
                });
                if (dadosProfissionais.length > 0) {
                    dados['Profissionais'] = dadosProfissionais.join('\n');
                }
            }

            // Etapas
            if (obra.etapas && obra.etapas.length > 0) {
                const dadosEtapas = obra.etapas.map(e => {
                    const partes = [];
                    if (document.getElementById('checkEtapasTipo').checked) {
                        partes.push(e.tipo);
                    }
                    if (document.getElementById('checkEtapasData').checked) {
                        partes.push(e.data);
                    }
                    if (document.getElementById('checkEtapasStatus').checked) {
                        partes.push(e.status);
                    }
                    if (document.getElementById('checkEtapasFotos').checked) {
                        partes.push(`${e.fotos?.length || 0} fotos`);
                    }
                    return partes.join(' - ');
                });
                if (dadosEtapas.length > 0) {
                    dados['Etapas'] = dadosEtapas.join('\n');
                }
            }

            // Visitas
            if (obra.visitas && obra.visitas.length > 0) {
                const dadosVisitas = obra.visitas.map(v => {
                    const partes = [];
                    if (document.getElementById('checkVisitasData').checked) {
                        partes.push(new Date(v.data).toLocaleDateString('pt-BR'));
                    }
                    if (document.getElementById('checkVisitasResponsavel').checked) {
                        partes.push(`Resp: ${v.responsavel}`);
                    }
                    if (document.getElementById('checkVisitasStatus').checked) {
                        partes.push(`Status: ${v.status}`);
                    }
                    if (document.getElementById('checkVisitasObservacoes').checked && v.observacoes) {
                        partes.push(`Obs: ${v.observacoes}`);
                    }
                    if (document.getElementById('checkVisitasFotos').checked) {
                        partes.push(`${v.fotos?.length || 0} fotos`);
                    }
                    return partes.join(' - ');
                });
                if (dadosVisitas.length > 0) {
                    dados['Visitas'] = dadosVisitas.join('\n');
                }
            }

            return dados;
        });

        if (dadosRelatorio.length === 0) {
            alert('Nenhuma obra encontrada no período selecionado');
            return;
        }

        if (filtros.formato === 'dashboard') {
            mostrarDashboard(dadosRelatorio);
        } else if (filtros.formato === 'excel') {
            // Gerar Excel
            const wb = XLSX.utils.book_new();
            const ws = XLSX.utils.json_to_sheet(dadosRelatorio);
            
            // Ajustar largura das colunas
            const colunas = Object.keys(dadosRelatorio[0]);
            const larguras = {};
            colunas.forEach(col => {
                larguras[col] = Math.max(
                    col.length,
                    ...dadosRelatorio.map(d => String(d[col]).length)
            });
            ws['!cols'] = colunas.map(col => ({ wch: larguras[col] }));

            XLSX.utils.book_append_sheet(wb, ws, "Relatório de Obras");
            XLSX.writeFile(wb, `relatorio_obras_${filtros.dataInicio}_${filtros.dataFim}.xlsx`);
        } else {
            // Gerar PDF
            const doc = new jsPDF();
            
            // Configurar cabeçalho
            doc.setFontSize(16);
            doc.text("Relatório de Obras", 14, 15);
            doc.setFontSize(10);
            doc.text(`Período: ${filtros.dataInicio} a ${filtros.dataFim}`, 14, 25);
            
            // Adicionar dados
            let y = 35;
            dadosRelatorio.forEach((obra, index) => {
                if (y > 250) {
                    doc.addPage();
                    y = 20;
                }
                
                doc.setFontSize(12);
                doc.text(`Obra ${obra['Número da Obra']}`, 14, y);
                y += 7;
                
                doc.setFontSize(10);
                Object.entries(obra).forEach(([campo, valor]) => {
                    if (campo !== 'Número da Obra') {
                        doc.text(`${campo}: ${valor}`, 14, y);
                        y += 5;
                    }
                });
                
                y += 5;
            });
            
            doc.save(`relatorio_obras_${filtros.dataInicio}_${filtros.dataFim}.pdf`);
        }

        alert('Relatório gerado com sucesso!');
    } catch (error) {
        console.error('Erro ao gerar relatório:', error);
        alert('Erro ao gerar relatório. Tente novamente.');
    } finally {
        btnGerar.disabled = false;
        btnGerar.innerHTML = '<i class="fas fa-file-export"></i> Gerar Relatório';
    }
}

// Inicializar quando o documento estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    inicializarRelatorios();
});

// Funções para gerenciar profissionais, vendedores, momentos e visitas
function inicializarBotoes() {
    // Adicionar Profissional
    document.getElementById('adicionarProfissional').addEventListener('click', function() {
        const container = document.getElementById('profissionais-container');
        const profissionalDiv = document.createElement('div');
        profissionalDiv.className = 'profissional-item mb-3 p-3 border rounded';
        profissionalDiv.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h5 class="mb-0">Profissional</h5>
                <button type="button" class="btn btn-danger btn-sm remover-profissional">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
            <div class="row">
                <div class="col-md-6 mb-2">
                    <input type="text" class="form-control" placeholder="Nome do Profissional" required>
                </div>
                <div class="col-md-6 mb-2">
                    <input type="tel" class="form-control telefone-input" placeholder="(00) 00000-0000" required 
                           maxlength="15" pattern="\\([0-9]{2}\\) [0-9]{4,5}-[0-9]{4}">
                </div>
                <div class="col-12">
                    <select class="form-select" required>
                        <option value="">Selecione a Especialidade</option>
                        <option value="arquiteto">Arquiteto</option>
                        <option value="engenheiro_civil">Engenheiro Civil</option>
                        <option value="engenheiro_eletrico">Engenheiro Elétrico</option>
                        <option value="designer_interiores">Designer de Interiores</option>
                        <option value="mestre_obras">Mestre de Obras</option>
                        <option value="pedreiro">Pedreiro</option>
                        <option value="carpinteiro">Carpinteiro</option>
                        <option value="eletricista">Eletricista</option>
                        <option value="encanador">Encanador</option>
                        <option value="pintor">Pintor</option>
                        <option value="gesseiro">Gesseiro</option>
                        <option value="marceneiro">Marceneiro</option>
                        <option value="serralheiro">Serralheiro</option>
                        <option value="vidraceiro">Vidraceiro</option>
                        <option value="impermeabilizador">Impermeabilizador</option>
                        <option value="paisagista">Paisagista</option>
                        <option value="decorador">Decorador</option>
                        <option value="projetista">Projetista</option>
                        <option value="tecnico_edificacoes">Técnico em Edificações</option>
                        <option value="instalador_ar">Instalador de Ar Condicionado</option>
                    </select>
                </div>
            </div>
        `;

        container.appendChild(profissionalDiv);
        
        // Adicionar máscara de telefone
        const telefoneInput = profissionalDiv.querySelector('.telefone-input');
        telefoneInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            if (value.length > 11) value = value.slice(0, 11);
            
            if (value.length > 0) {
                value = '(' + value;
                if (value.length > 3) {
                    value = value.slice(0, 3) + ') ' + value.slice(3);
                }
                if (value.length > 10) {
                    value = value.slice(0, 10) + '-' + value.slice(10);
                }
            }
            e.target.value = value;
        });

        // Evento para remover profissional
        profissionalDiv.querySelector('.remover-profissional').addEventListener('click', function() {
            profissionalDiv.remove();
        });
    });

    // Adicionar Vendedor
    const btnAdicionarVendedor = document.getElementById('adicionarVendedor');
    const vendedoresContainer = document.getElementById('vendedores-container');
    const templateVendedor = document.getElementById('template-vendedor');

    if (btnAdicionarVendedor && vendedoresContainer && templateVendedor) {
        btnAdicionarVendedor.addEventListener('click', function() {
            const novoVendedor = templateVendedor.content.cloneNode(true);
            
            // Configurar evento de remoção
            novoVendedor.querySelector('.remover-vendedor').addEventListener('click', function(e) {
                if(confirm('Tem certeza que deseja remover este vendedor?')) {
                    e.target.closest('.vendedor-item').remove();
                }
            });

            vendedoresContainer.appendChild(novoVendedor);
        });
    }

    // Adicionar array com a ordem dos momentos
    const momentosOrdenados = [
        { valor: 'projeto', texto: 'Elaboração de Projeto' },
        { valor: 'preliminares', texto: 'Serviços Preliminares' },
        { valor: 'estrutura', texto: 'Estrutura e Fundações' },
        { valor: 'vedacoes', texto: 'Vedações Verticais' },
        { valor: 'impermeabilizacao', texto: 'Impermeabilização' },
        { valor: 'paredes', texto: 'Paredes' },
        { valor: 'telhados', texto: 'Telhados' },
        { valor: 'hidraulica', texto: 'Instalações Hidráulicas' },
        { valor: 'eletrica', texto: 'Instalações Elétricas' },
        { valor: 'complementares', texto: 'Instalações Complementares' },
        { valor: 'pisos', texto: 'Pisos e Porcelanatos' },
        { valor: 'pinturas', texto: 'Pinturas e Finalizações' },
        { valor: 'esquadrias', texto: 'Esquadrias' },
        { valor: 'loucas', texto: 'Louças e Metais' },
        { valor: 'limpeza', texto: 'Limpeza e Entrega' }
    ];

    // Atualizar a função de adicionar momento
    document.getElementById('adicionarMomento').addEventListener('click', function() {
        const container = document.getElementById('momentos-container');
        
        // Verificar momentos já utilizados
        const momentosUtilizados = Array.from(container.querySelectorAll('select'))
            .map(select => select.value)
            .filter(valor => valor !== '');

        // Filtrar momentos disponíveis
        const momentosDisponiveis = momentosOrdenados.filter(momento => 
            !momentosUtilizados.includes(momento.valor)
        );

        if (momentosDisponiveis.length === 0) {
            alert('Todos os momentos já foram adicionados!');
            return;
        }

        const momentoDiv = document.createElement('div');
        momentoDiv.className = 'momento-item mb-3 p-3 border rounded';
        momentoDiv.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h5 class="mb-0">Momento da Obra</h5>
                <button type="button" class="btn btn-danger btn-sm remover-momento">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
            <div class="row mb-3">
                <div class="col-md-6">
                    <select class="form-select momento-select" required>
                        <option value="">Selecione o Momento</option>
                        ${momentosDisponiveis.map(momento => 
                            `<option value="${momento.valor}">${momento.texto}</option>`
                        ).join('')}
                    </select>
                </div>
                <div class="col-md-6">
                    <select class="form-select" required>
                        <option value="">Status</option>
                        <option value="nao_iniciado">Não Iniciado</option>
                        <option value="em_andamento">Em Andamento</option>
                        <option value="concluido">Concluído</option>
                    </select>
                </div>
            </div>
            <div class="row mb-3">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header bg-light">
                            <label class="form-label mb-0">
                                <i class="fas fa-camera"></i> Foto do Momento
                            </label>
                        </div>
                        <div class="card-body">
                            <div class="upload-area mb-2">
                                <input type="file" class="form-control" accept="image/*">
                                <small class="text-muted d-block mt-1">
                                    Formato: JPG, PNG (Máx: 5MB)
                                </small>
                            </div>
                            <div class="preview-container" style="display: none;">
                                <div class="position-relative">
                                    <img src="" class="img-fluid rounded" style="max-height: 200px;">
                                    <button type="button" class="btn btn-sm btn-light position-absolute top-0 end-0 m-2 preview-btn">
                                        <i class="fas fa-expand"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="fornecedores-container">
                <div class="fornecedores-list">
                    <!-- Fornecedores serão adicionados aqui -->
                </div>
                <button type="button" class="btn btn-sm btn-success adicionar-fornecedor">
                    <i class="fas fa-plus"></i> Adicionar Fornecedor
                </button>
            </div>
        `;

        container.appendChild(momentoDiv);

        // Ordenar momentos após adicionar novo
        const momentosItems = Array.from(container.children);
        momentosItems.sort((a, b) => {
            const valorA = a.querySelector('.momento-select').value;
            const valorB = b.querySelector('.momento-select').value;
            const indexA = momentosOrdenados.findIndex(m => m.valor === valorA);
            const indexB = momentosOrdenados.findIndex(m => m.valor === valorB);
            return indexA - indexB;
        });

        momentosItems.forEach(item => container.appendChild(item));

        // Evento para remover momento
        momentoDiv.querySelector('.remover-momento').addEventListener('click', function() {
            momentoDiv.remove();
        });

        // Evento para preview da imagem
        const input = momentoDiv.querySelector('input[type="file"]');
        const previewContainer = momentoDiv.querySelector('.preview-container');
        const previewImg = previewContainer.querySelector('img');
        const previewBtn = previewContainer.querySelector('.preview-btn');

        input.addEventListener('change', function(e) {
            if (this.files && this.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    previewImg.src = e.target.result;
                    previewContainer.style.display = 'block';
                };
                reader.readAsDataURL(this.files[0]);
            }
        });

        previewBtn.addEventListener('click', function() {
            // Implementar visualização em tela cheia se necessário
            previewContainer.style.display = previewContainer.style.display === 'none' ? 'block' : 'none';
        });

        // Evento para adicionar fornecedor
        momentoDiv.querySelector('.adicionar-fornecedor').addEventListener('click', function() {
            const fornecedoresList = this.previousElementSibling;
            const fornecedorDiv = document.createElement('div');
            fornecedorDiv.className = 'input-group mb-2';
            fornecedorDiv.innerHTML = `
                <input type="text" class="form-control" placeholder="Nome do fornecedor">
                <button type="button" class="btn btn-danger remover-fornecedor">
                    <i class="fas fa-minus"></i>
                </button>
            `;

            fornecedoresList.appendChild(fornecedorDiv);

            // Evento para remover fornecedor
            fornecedorDiv.querySelector('.remover-fornecedor').addEventListener('click', function() {
                fornecedorDiv.remove();
            });
        });
    });

    // Adicionar evento para reordenar ao mudar seleção
    document.addEventListener('change', function(e) {
        if (e.target.classList.contains('momento-select')) {
            const container = document.getElementById('momentos-container');
            const momentosItems = Array.from(container.children);
            momentosItems.sort((a, b) => {
                const valorA = a.querySelector('.momento-select').value;
                const valorB = b.querySelector('.momento-select').value;
                const indexA = momentosOrdenados.findIndex(m => m.valor === valorA);
                const indexB = momentosOrdenados.findIndex(m => m.valor === valorB);
                return indexA - indexB;
            });

            momentosItems.forEach(item => container.appendChild(item));
        }
    });

    // Nova Visita
    document.getElementById('novaVisita').addEventListener('click', function() {
        const container = document.getElementById('visitas-container');
        const visitaDiv = document.createElement('div');
        visitaDiv.className = 'visita-item mb-4';
        visitaDiv.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5 class="mb-0">Visita</h5>
                <button type="button" class="btn btn-danger btn-sm remover-visita">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
            <div class="row">
                <div class="col-md-4 mb-3">
                    <label class="form-label">Data da Visita</label>
                    <input type="date" class="form-control" required>
                </div>
                <div class="col-md-4 mb-3">
                    <label class="form-label">Responsável</label>
                    <input type="text" class="form-control" placeholder="Nome do responsável" required>
                </div>
                <div class="col-md-4 mb-3">
                    <label class="form-label">Status da Obra</label>
                    <select class="form-select" required>
                        <option value="">Selecione</option>
                        <option value="em_andamento">Em Andamento</option>
                        <option value="paralisada">Paralisada</option>
                        <option value="concluida">Concluída</option>
                    </select>
                </div>
            </div>
            <div class="row">
                <div class="col-12 mb-3">
                    <label class="form-label">Observações</label>
                    <textarea class="form-control" rows="3"></textarea>
                </div>
            </div>
            <div class="row mb-4">
                <div class="col-12">
                    <h5 class="border-bottom pb-2 mb-3">Registro Fotográfico</h5>
                </div>
                <div class="col-md-6">
                    <div class="card h-100">
                        <div class="card-header bg-light">
                            <label class="form-label mb-0">
                                <i class="fas fa-camera"></i> Foto Atual <span class="text-danger">*</span>
                            </label>
                        </div>
                        <div class="card-body">
                            <div class="upload-area mb-2">
                                <input type="file" class="form-control" accept="image/*" required>
                                <small class="text-muted d-block mt-1">
                                    Formato: JPG, PNG (Máx: 5MB)
                                </small>
                            </div>
                            <div class="preview-container" style="display: none;">
                                <div class="position-relative">
                                    <img src="" class="img-fluid rounded" style="max-height: 200px;">
                                    <button type="button" class="btn btn-sm btn-light position-absolute top-0 end-0 m-2 preview-btn">
                                        <i class="fas fa-expand"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card h-100">
                        <div class="card-header bg-light">
                            <label class="form-label mb-0">
                                <i class="fas fa-camera"></i> Foto Depois
                            </label>
                        </div>
                        <div class="card-body">
                            <div class="upload-area mb-2">
                                <input type="file" class="form-control" accept="image/*">
                                <small class="text-muted d-block mt-1">
                                    Formato: JPG, PNG (Máx: 5MB)
                                </small>
                            </div>
                            <div class="preview-container" style="display: none;">
                                <div class="position-relative">
                                    <img src="" class="img-fluid rounded" style="max-height: 200px;">
                                    <button type="button" class="btn btn-sm btn-light position-absolute top-0 end-0 m-2 preview-btn">
                                        <i class="fas fa-expand"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row">
                <div class="col-12">
                    <label class="form-label">Palavras-chave</label>
                    <div class="input-group">
                        <input type="text" class="form-control tag-input" 
                               placeholder="Digite uma palavra-chave e pressione Enter">
                        <button class="btn btn-outline-secondary add-tag" type="button">
                            <i class="fas fa-plus"></i>
                        </button>
                    </div>
                    <div class="tags-container mt-2"></div>
                    <small class="text-muted">Adicione palavras-chave para facilitar a busca posterior</small>
                </div>
            </div>
        `;

        container.appendChild(visitaDiv);
        
        // Evento para remover visita
        visitaDiv.querySelector('.remover-visita').addEventListener('click', function() {
            visitaDiv.remove();
        });

        // Sistema de tags
        const tagInput = visitaDiv.querySelector('.tag-input');
        const addTagBtn = visitaDiv.querySelector('.add-tag');
        const tagsContainer = visitaDiv.querySelector('.tags-container');
        let tags = [];

        function adicionarTag(tag) {
            tag = tag.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
            if (tag && !tags.includes(tag)) {
                tags.push(tag);
                atualizarTags();
            }
            tagInput.value = '';
        }

        function atualizarTags() {
            tagsContainer.innerHTML = tags.map(tag => `
                <span class="badge bg-primary me-1 mb-1">
                    ${tag}
                    <i class="fas fa-times ms-1" style="cursor: pointer;" 
                       onclick="this.parentElement.remove(); tags = tags.filter(t => t !== '${tag}');"></i>
                </span>
            `).join('');
        }

        tagInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                adicionarTag(this.value);
            }
        });

        addTagBtn.addEventListener('click', function() {
            adicionarTag(tagInput.value);
        });

        // Adicionar eventos para preview das imagens
        visitaDiv.querySelectorAll('input[type="file"]').forEach(input => {
            const previewBtn = input.nextElementSibling;
            const previewContainer = input.parentElement.nextElementSibling;
            const previewImg = previewContainer.querySelector('img');

            input.addEventListener('change', function(e) {
                if (this.files && this.files[0]) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        previewImg.src = e.target.result;
                    };
                    reader.readAsDataURL(this.files[0]);
                    previewContainer.style.display = 'block';
                }
            });

            previewBtn.addEventListener('click', function() {
                previewContainer.style.display = previewContainer.style.display === 'none' ? 'block' : 'none';
            });
        });
    });
}

// Inicializar todos os botões quando o documento estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    inicializarBotoes();
});

// Função para gerenciar favoritos
function inicializarFavoritos() {
    const btnFavorite = document.getElementById('btnFavorite');
    const starIcon = btnFavorite.querySelector('i');

    // Função para atualizar visual do botão
    function atualizarBotaoFavorito(isFavorite) {
        if (isFavorite) {
            starIcon.classList.add('text-warning');
            starIcon.classList.remove('text-muted');
        } else {
            starIcon.classList.add('text-muted');
            starIcon.classList.remove('text-warning');
        }
    }

    // Verificar estado inicial
    function verificarFavorito(numeroObra) {
        const favoritos = JSON.parse(localStorage.getItem('obrasFavoritas') || '[]');
        return favoritos.includes(numeroObra);
    }

    // Alternar favorito
    btnFavorite.addEventListener('click', function() {
        const numeroObra = document.getElementById('numeroObra').value;
        if (!numeroObra) {
            alert('Por favor, selecione ou crie uma obra primeiro.');
            return;
        }

        const favoritos = JSON.parse(localStorage.getItem('obrasFavoritas') || '[]');
        const index = favoritos.indexOf(numeroObra);
        
        if (index > -1) {
            favoritos.splice(index, 1); // Remove dos favoritos
            atualizarBotaoFavorito(false);
        } else {
            favoritos.push(numeroObra); // Adiciona aos favoritos
            atualizarBotaoFavorito(true);
        }
        
        localStorage.setItem('obrasFavoritas', JSON.stringify(favoritos));
    });

    // Atualizar estado do botão quando uma obra é carregada
    document.getElementById('numeroObra').addEventListener('change', function() {
        const isFavorite = verificarFavorito(this.value);
        atualizarBotaoFavorito(isFavorite);
    });

    // Estado inicial
    atualizarBotaoFavorito(false);
}

// Inicializar favoritos quando o documento estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    inicializarFavoritos();
});

// Função para gerar dashboards
async function mostrarDashboard(dados) {
    // Criar modal para o dashboard
    const modalHTML = `
        <div class="modal fade" id="dashboardModal" tabindex="-1">
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Dashboard de Obras</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <!-- Resumo Geral -->
                            <div class="col-md-12 mb-4">
                                <div class="card">
                                    <div class="card-body">
                                        <h6 class="card-title">Resumo Geral</h6>
                                        <div class="row" id="resumoGeral"></div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Gráficos -->
                            <div class="col-md-6 mb-4">
                                <div class="card">
                                    <div class="card-body">
                                        <h6 class="card-title">Status das Obras</h6>
                                        <canvas id="graficoStatus"></canvas>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="col-md-6 mb-4">
                                <div class="card">
                                    <div class="card-body">
                                        <h6 class="card-title">Profissionais por Especialidade</h6>
                                        <canvas id="graficoProfissionais"></canvas>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="col-md-12 mb-4">
                                <div class="card">
                                    <div class="card-body">
                                        <h6 class="card-title">Evolução de Obras</h6>
                                        <canvas id="graficoEvolucao"></canvas>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-primary" onclick="exportarDashboardPDF()">
                            Exportar como PDF
                        </button>
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fechar</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Adicionar modal ao documento
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Processar dados para os gráficos
    const resumo = {
        totalObras: dados.length,
        emAndamento: dados.filter(d => d.Status === 'Em Andamento').length,
        concluidas: dados.filter(d => d.Status === 'Concluída').length
    };

    // Atualizar resumo geral
    document.getElementById('resumoGeral').innerHTML = `
        <div class="col-md-4">
            <div class="text-center">
                <h3>${resumo.totalObras}</h3>
                <p>Total de Obras</p>
            </div>
        </div>
        <div class="col-md-4">
            <div class="text-center">
                <h3>${resumo.emAndamento}</h3>
                <p>Em Andamento</p>
            </div>
        </div>
        <div class="col-md-4">
            <div class="text-center">
                <h3>${resumo.concluidas}</h3>
                <p>Concluídas</p>
            </div>
        </div>
    `;

    // Criar gráficos
    const ctxStatus = document.getElementById('graficoStatus').getContext('2d');
    new Chart(ctxStatus, {
        type: 'pie',
        data: {
            labels: ['Em Andamento', 'Concluídas', 'Outros'],
            datasets: [{
                data: [resumo.emAndamento, resumo.concluidas, 
                       resumo.totalObras - resumo.emAndamento - resumo.concluidas],
                backgroundColor: ['#ffc107', '#28a745', '#dc3545']
            }]
        }
    });

    // Gráfico de profissionais
    const profissionaisPorEspecialidade = {};
    dados.forEach(obra => {
        if (obra.Profissionais) {
            obra.Profissionais.split('\n').forEach(prof => {
                const especialidade = prof.match(/\((.*?)\)/)?.[1] || 'Outros';
                profissionaisPorEspecialidade[especialidade] = 
                    (profissionaisPorEspecialidade[especialidade] || 0) + 1;
            });
        }
    });

    const ctxProf = document.getElementById('graficoProfissionais').getContext('2d');
    new Chart(ctxProf, {
        type: 'bar',
        data: {
            labels: Object.keys(profissionaisPorEspecialidade),
            datasets: [{
                label: 'Quantidade',
                data: Object.values(profissionaisPorEspecialidade),
                backgroundColor: '#007bff'
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });

    // Gráfico de evolução
    const evolucaoPorMes = {};
    dados.forEach(obra => {
        const mes = new Date(obra['Data de Início']).toLocaleDateString('pt-BR', {
            year: 'numeric',
            month: 'short'
        });
        evolucaoPorMes[mes] = (evolucaoPorMes[mes] || 0) + 1;
    });

    const ctxEvol = document.getElementById('graficoEvolucao').getContext('2d');
    new Chart(ctxEvol, {
        type: 'line',
        data: {
            labels: Object.keys(evolucaoPorMes),
            datasets: [{
                label: 'Novas Obras',
                data: Object.values(evolucaoPorMes),
                borderColor: '#20c997',
                tension: 0.1
            }]
        }
    });

    // Gráfico de visitas
    if (dados.some(d => d.Visitas)) {
        const visitasPorMes = {};
        dados.forEach(obra => {
            if (obra.Visitas) {
                obra.Visitas.split('\n').forEach(visita => {
                    const dataVisita = visita.match(/(\d{2}\/\d{2}\/\d{4})/)?.[1];
                    if (dataVisita) {
                        const mes = new Date(dataVisita.split('/').reverse().join('-'))
                            .toLocaleDateString('pt-BR', {
                                year: 'numeric',
                                month: 'short'
                            });
                        visitasPorMes[mes] = (visitasPorMes[mes] || 0) + 1;
                    }
                });
            }
        });

        // Adicionar div para o gráfico de visitas no modal
        const visitasDiv = document.createElement('div');
        visitasDiv.className = 'col-md-12 mb-4';
        visitasDiv.innerHTML = `
            <div class="card">
                <div class="card-body">
                    <h6 class="card-title">Visitas por Mês</h6>
                    <canvas id="graficoVisitas"></canvas>
                </div>
            </div>
        `;
        document.querySelector('#dashboardModal .modal-body .row').appendChild(visitasDiv);

        // Criar gráfico de visitas
        const ctxVisitas = document.getElementById('graficoVisitas').getContext('2d');
        new Chart(ctxVisitas, {
            type: 'bar',
            data: {
                labels: Object.keys(visitasPorMes),
                datasets: [{
                    label: 'Quantidade de Visitas',
                    data: Object.values(visitasPorMes),
                    backgroundColor: '#6f42c1',
                    borderColor: '#6f42c1',
                    borderWidth: 1
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                }
            }
        });

        // Atualizar resumo geral para incluir total de visitas
        const totalVisitas = Object.values(visitasPorMes).reduce((a, b) => a + b, 0);
        const resumoVisitas = document.createElement('div');
        resumoVisitas.className = 'col-md-4';
        resumoVisitas.innerHTML = `
            <div class="text-center">
                <h3>${totalVisitas}</h3>
                <p>Total de Visitas</p>
            </div>
        `;
        document.getElementById('resumoGeral').appendChild(resumoVisitas);
    }

    // Mostrar modal
    const modal = new bootstrap.Modal(document.getElementById('dashboardModal'));
    modal.show();
}

async function exportarDashboardPDF() {
    const modal = document.getElementById('dashboardModal');
    
    // Usar html2canvas para capturar o dashboard
    const canvas = await html2canvas(modal.querySelector('.modal-body'));
    
    // Criar PDF
    const pdf = new jsPDF('l', 'mm', 'a4');
    pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 10, 10, 277, 190);
    pdf.save('dashboard.pdf');
}

// Função para calcular progresso do cadastro
function calcularProgressoCadastro() {
    let totalCampos = 0;
    let camposPreenchidos = 0;

    // Atualizar a lista de campos básicos obrigatórios
    const basicosObrigatorios = [
        'nome',
        'cpf',
        'email',
        'telefone',
        'tipoObra',
        'padraoObra',
        'potencialObra'
    ];
    let basicosPreenchidos = 0;
    basicosObrigatorios.forEach(campo => {
        if (document.getElementById(campo)?.value) {
            basicosPreenchidos++;
        }
    });
    camposPreenchidos += (basicosPreenchidos / basicosObrigatorios.length) * 20;
    totalCampos += 20;

    // Informações do Profissional (20%)
    const profissionais = document.querySelectorAll('.profissional-item');
    if (profissionais.length > 0) {
        let profissionaisValidos = 0;
        profissionais.forEach(prof => {
            const nome = prof.querySelector('.profissional-nome').value;
            const especialidade = prof.querySelector('.profissional-especialidade').value;
            const telefone = prof.querySelector('.profissional-telefone').value;
            if (nome && especialidade && telefone) {
                profissionaisValidos++;
            }
        });
        if (profissionaisValidos > 0) camposPreenchidos += 20;
    }
    totalCampos += 20;

    // Atualizar a lista de campos de detalhes obrigatórios
    const detalhesObrigatorios = [
        'logradouro',
        'numero',
        'bairro',
        'cidade',
        'estado',
        'cep'
    ];
    let detalhesPreenchidos = 0;
    detalhesObrigatorios.forEach(campo => {
        if (document.getElementById(campo)?.value) {
            detalhesPreenchidos++;
        }
    });
    camposPreenchidos += (detalhesPreenchidos / detalhesObrigatorios.length) * 20;
    totalCampos += 20;

    // Etapas da Obra (20%)
    const etapas = document.querySelectorAll('.etapa-item');
    if (etapas.length > 0) {
        let etapasValidas = 0;
        etapas.forEach(etapa => {
            const data = etapa.querySelector('.etapa-data').value;
            const tipo = etapa.querySelector('.etapa-tipo').value;
            const fornecedores = etapa.querySelectorAll('.fornecedor-item');
            if (data && tipo && fornecedores.length > 0) {
                etapasValidas++;
            }
        });
        if (etapasValidas > 0) camposPreenchidos += 20;
    }
    totalCampos += 20;

    // Visitas à Obra (20%)
    const visitas = document.querySelectorAll('.visita-item');
    if (visitas.length > 0) {
        let visitasValidas = 0;
        visitas.forEach(visita => {
            const data = visita.querySelector('.visita-data').value;
            const responsavel = visita.querySelector('.visita-responsavel').value;
            const status = visita.querySelector('.visita-status').value;
            const observacoes = visita.querySelector('.visita-observacoes').value;
            if (data && responsavel && status && observacoes) {
                visitasValidas++;
            }
        });
        if (visitasValidas > 0) camposPreenchidos += 20;
    }
    totalCampos += 20;

    // Calcular porcentagem total
    return Math.round((camposPreenchidos / totalCampos) * 100);
}

// Atualizar o HTML da barra de progresso
const progressHtml = `
<div class="card mb-3">
    <div class="card-body">
        <h5 class="card-title">Progresso do Cadastro</h5>
        <div class="progress" style="height: 25px;">
            <div class="progress-bar" role="progressbar" 
                 style="width: 0%" 
                 aria-valuenow="0" 
                 aria-valuemin="0" 
                 aria-valuemax="100">0%</div>
        </div>
        <div class="mt-2">
            <small class="text-muted">Campos obrigatórios:</small>
            <ul class="list-unstyled small">
                <li><i class="fas fa-check-circle text-success"></i> Informações Básicas (20%)</li>
                <li><i class="fas fa-check-circle text-success"></i> Informações do Profissional (20%)</li>
                <li><i class="fas fa-check-circle text-success"></i> Detalhes da Obra (20%)</li>
                <li><i class="fas fa-check-circle text-success"></i> Etapas da Obra (20%)</li>
                <li><i class="fas fa-check-circle text-success"></i> Visitas à Obra (20%)</li>
            </ul>
        </div>
    </div>
</div>
`;

// Inserir barra de progresso antes dos botões de ação
document.querySelector('.d-flex.flex-wrap.gap-2.mb-4').insertAdjacentHTML('beforebegin', progressHtml);

// Adicionar listeners para atualizar progresso
document.querySelectorAll('input, select, textarea').forEach(elemento => {
    elemento.addEventListener('change', atualizarBarraProgresso);
});

// Atualizar quando adicionar/remover itens
['profissionais-container', 'vendedores-container', 'etapas-container', 'visitas-container'].forEach(containerId => {
    const observer = new MutationObserver(atualizarBarraProgresso);
    observer.observe(document.getElementById(containerId), { childList: true, subtree: true });
});

// Atualizar progresso inicial
atualizarBarraProgresso();

// Função para atualizar barra de progresso
function atualizarBarraProgresso() {
    const progresso = calcularProgressoCadastro();
    const progressBar = document.querySelector('.progress-bar');
    progressBar.style.width = `${progresso}%`;
    progressBar.setAttribute('aria-valuenow', progresso);
    progressBar.textContent = `${progresso}%`;

    // Atualizar cor baseado no progresso
    if (progresso < 33) {
        progressBar.classList.remove('bg-warning', 'bg-success');
        progressBar.classList.add('bg-danger');
    } else if (progresso < 66) {
        progressBar.classList.remove('bg-danger', 'bg-success');
        progressBar.classList.add('bg-warning');
    } else {
        progressBar.classList.remove('bg-danger', 'bg-warning');
        progressBar.classList.add('bg-success');
    }

    // Atualizar o botão de salvar baseado no progresso
    verificarProgressoSalvar();
}

// Adicionar função para verificar progresso
function verificarProgressoSalvar() {
    const progressBar = document.querySelector('.progress-bar');
    const btnSalvar = document.querySelector('button[type="submit"]');
    
    if (progressBar) {
        const progresso = parseInt(progressBar.style.width) || 0;
        
        if (progresso < 50) {
            btnSalvar.disabled = true;
            btnSalvar.title = 'Complete pelo menos 50% do cadastro para salvar';
            
            // Adicionar alerta visual
            if (!document.getElementById('alertaProgresso')) {
                const alerta = document.createElement('div');
                alerta.id = 'alertaProgresso';
                alerta.className = 'alert alert-warning mt-2';
                alerta.innerHTML = 'Complete pelo menos 50% do cadastro para salvar a obra';
                btnSalvar.parentNode.insertBefore(alerta, btnSalvar.nextSibling);
            }
        } else {
            btnSalvar.disabled = false;
            btnSalvar.title = 'Salvar obra';
            
            // Remover alerta se existir
            const alerta = document.getElementById('alertaProgresso');
            if (alerta) alerta.remove();
        }
    }
}

// Adicionar verificação inicial quando a página carregar
document.addEventListener('DOMContentLoaded', function() {
    verificarProgressoSalvar();
});

// Função para obter o próximo número de obra
function getProximoNumeroObra() {
    const obras = JSON.parse(localStorage.getItem('obras') || '{}');
    let maxNumero = 0;
    
    // Encontrar o maior número atual
    Object.keys(obras).forEach(numeroObra => {
        const numero = parseInt(numeroObra);
        if (!isNaN(numero) && numero > maxNumero) {
            maxNumero = numero;
        }
    });
    
    // Retornar próximo número
    return (maxNumero + 1).toString().padStart(4, '0');
}

// Atualizar o evento do campo número da obra
document.getElementById('numeroObra').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        
        // Se o campo estiver vazio ou já tem um número
        const novoNumero = getProximoNumeroObra();
        this.value = novoNumero;
        
        // Feedback visual
        const feedback = document.getElementById('obraFeedback');
        feedback.textContent = `Nova obra criada com número ${novoNumero}`;
        feedback.style.color = 'green';
        
        // Limpar feedback após 3 segundos
        setTimeout(() => {
            feedback.textContent = '';
        }, 3000);
        
        // Habilitar edição
        document.getElementById('btnAlterar').style.display = 'none';
        this.readOnly = false;
        
        // Limpar formulário mantendo o responsável
        const responsavel = document.getElementById('responsavelCadastro').value;
        document.getElementById('obraForm').reset();
        
        // Restaurar valores após reset
        this.value = novoNumero;
        document.getElementById('responsavelCadastro').value = responsavel;
        
        // Limpar containers dinâmicos
        ['profissionais-container', 'vendedores-container', 'momentos-container', 'visitas-container'].forEach(id => {
            document.getElementById(id).innerHTML = '';
        });
        
        // Resetar mapa se existir
        if (typeof map !== 'undefined') {
            map.setCenter({ lat: -15.7801, lng: -47.9292 });
            map.setZoom(4);
            if (marker) {
                marker.setPosition({ lat: -15.7801, lng: -47.9292 });
            }
        }
        
        // Focar no próximo campo após o número da obra
        document.getElementById('logradouro').focus();
    }
});

// Função para gerenciar o responsável pelo cadastro
function inicializarResponsavelCadastro() {
    const inputResponsavel = document.getElementById('responsavelCadastro');
    
    // Recuperar último responsável usado
    const ultimoResponsavel = localStorage.getItem('ultimoResponsavel');
    if (ultimoResponsavel) {
        inputResponsavel.value = ultimoResponsavel;
    }
    
    // Salvar responsável quando alterado
    inputResponsavel.addEventListener('change', function() {
        if (this.value.trim()) {
            localStorage.setItem('ultimoResponsavel', this.value.trim());
        }
    });
    
    // Não limpar o responsável quando o formulário for resetado
    document.getElementById('obraForm').addEventListener('reset', function(e) {
        setTimeout(() => {
            inputResponsavel.value = localStorage.getItem('ultimoResponsavel') || '';
        }, 0);
    });
}

// Inicializar quando o documento estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    inicializarResponsavelCadastro();
});

// Adicionar função para validar e-mail
function validarEmail(email) {
    const regex = /^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}$/;
    return regex.test(email);
}

// Adicionar evento para o campo de e-mail
document.addEventListener('DOMContentLoaded', function() {
    const emailInput = document.getElementById('email');
    
    if (emailInput) {
        emailInput.addEventListener('input', function() {
            const email = this.value.trim();
            
            // Remover espaços
            this.value = email;
            
            // Validar formato
            if (email && !validarEmail(email)) {
                this.classList.add('is-invalid');
                this.classList.remove('is-valid');
            } else if (email) {
                this.classList.add('is-valid');
                this.classList.remove('is-invalid');
            } else {
                this.classList.remove('is-valid', 'is-invalid');
            }
        });

        // Validar ao perder o foco
        emailInput.addEventListener('blur', function() {
            const email = this.value.trim();
            if (email && !validarEmail(email)) {
                this.classList.add('is-invalid');
            }
        });
    }
});

// Adicionar função para buscar CEPs por logradouro
async function buscarCEPsPorLogradouro(logradouro, cidade, estado) {
    try {
        // Mostrar loading no botão
        const btnBuscar = document.getElementById('buscarPorLogradouro');
        btnBuscar.disabled = true;
        btnBuscar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Buscando...';

        // Formatar parâmetros para a URL
        const logradouroFormatado = encodeURIComponent(logradouro.replace(/[^a-zA-Z0-9\s]/g, ''));
        const cidadeFormatada = encodeURIComponent(cidade.replace(/[^a-zA-Z0-9\s]/g, ''));
        const estadoFormatado = encodeURIComponent(estado.toUpperCase().substring(0, 2));

        // Usar a API do ViaCEP
        const url = `https://viacep.com.br/ws/${estadoFormatado}/${cidadeFormatada}/${logradouroFormatado}/json/`;
        console.log('URL da busca:', url); // Para debug

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error('Erro na requisição');
        }

        const data = await response.json();
        
        if (Array.isArray(data) && data.length > 0) {
            // Filtrar CEPs válidos
            const cepsValidos = data.filter(cep => !cep.erro);
            if (cepsValidos.length > 0) {
                mostrarModalCEPs(cepsValidos);
            } else {
                alert('Nenhum CEP válido encontrado para este endereço');
            }
        } else {
            alert('Nenhum CEP encontrado para este endereço. Verifique os dados informados.');
        }
    } catch (error) {
        console.error('Erro ao buscar CEPs:', error);
        alert('Erro ao buscar CEPs. Verifique se os dados estão corretos e tente novamente.');
    } finally {
        // Restaurar botão
        const btnBuscar = document.getElementById('buscarPorLogradouro');
        btnBuscar.disabled = false;
        btnBuscar.innerHTML = '<i class="fas fa-search"></i> Buscar CEP';
    }
}

// Função para preencher os campos com os dados do CEP
function preencherCamposEndereco(cepData) {
    document.getElementById('cep').value = cepData.cep.replace(/\D/g, '');
    document.getElementById('logradouro').value = cepData.logradouro || '';
    document.getElementById('bairro').value = cepData.bairro || '';
    document.getElementById('cidade').value = cepData.localidade || '';
    document.getElementById('estado').value = cepData.uf || '';

    // Atualizar mapa
    const enderecoCompleto = `${cepData.logradouro}, ${cepData.bairro}, ${cepData.localidade}, ${cepData.uf}`;
    atualizarMapa(enderecoCompleto);
}

// Função para mostrar modal com lista de CEPs
function mostrarModalCEPs(ceps) {
    // Remover modal anterior se existir
    const modalAnterior = document.getElementById('modalCEPs');
    if (modalAnterior) {
        modalAnterior.remove();
    }

    // Criar modal dinamicamente
    const modalHtml = `
        <div class="modal fade" id="modalCEPs" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Selecione o CEP</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="list-group">
                            ${ceps.map(cep => `
                                <button type="button" class="list-group-item list-group-item-action" 
                                        data-cep='${JSON.stringify(cep)}'>
                                    <strong>CEP: ${cep.cep}</strong><br>
                                    ${cep.logradouro}, ${cep.bairro}<br>
                                    ${cep.localidade} - ${cep.uf}
                                </button>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Adicionar modal ao DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Configurar eventos
    const modal = new bootstrap.Modal(document.getElementById('modalCEPs'));
    
    document.querySelectorAll('#modalCEPs .list-group-item').forEach(item => {
        item.addEventListener('click', function() {
            const cepData = JSON.parse(this.dataset.cep);
            preencherCamposEndereco(cepData);
            modal.hide();
        });
    });

    // Mostrar modal
    modal.show();

    // Remover modal do DOM após fechar
    document.getElementById('modalCEPs').addEventListener('hidden.bs.modal', function() {
        this.remove();
    });
}

// Adicionar ao script.js existente
document.addEventListener('DOMContentLoaded', function() {
    // Configurar WhatsApp para o profissional
    const telefoneInput = document.querySelector('.profissional-telefone');
    const whatsappBtn = document.querySelector('.whatsapp-btn');
    const nomeInput = document.querySelector('.profissional-nome');
    const especialidadeSelect = document.querySelector('.profissional-especialidade');

    if (telefoneInput && whatsappBtn) {
        // Máscara do telefone
        telefoneInput.addEventListener('input', function() {
            let valor = this.value.replace(/\D/g, '');
            if (valor.length > 11) valor = valor.slice(0, 11);
            
            if (valor.length > 10) {
                valor = valor.replace(/^(\d{2})(\d{5})(\d{4})$/, '($1) $2-$3');
            } else if (valor.length > 6) {
                valor = valor.replace(/^(\d{2})(\d{4})(\d{0,4})$/, '($1) $2-$3');
            } else if (valor.length > 2) {
                valor = valor.replace(/^(\d{2})(\d{0,5})$/, '($1) $2');
            }
            
            this.value = valor;
            whatsappBtn.disabled = valor.replace(/\D/g, '').length < 10;
        });

        // Evento do botão WhatsApp
        whatsappBtn.addEventListener('click', function() {
            const numero = telefoneInput.value.replace(/\D/g, '');
            const nome = nomeInput.value.trim();
            const especialidade = especialidadeSelect.options[especialidadeSelect.selectedIndex].text;

            if (numero.length >= 10) {
                let numeroFormatado = numero;
                if (numero.length === 10) {
                    numeroFormatado = numero.substring(0, 2) + '9' + numero.substring(2);
                }

                const mensagem = encodeURIComponent(
                    `Olá ${nome}, ${especialidade}!\n\n` +
                    `Tudo bem?\n\n` +
                    `Agradecemos por compartilhar seu número conosco! Queremos fortalecer essa parceria e, para isso, ` +
                    `criamos um grupo exclusivo no WhatsApp onde você terá acesso às principais novidades, ` +
                    `lançamentos e ofertas diárias. Além disso, você ainda poderá concorrer a prêmios incríveis!\n\n` +
                    `Atenciosamente,\nEmpresa Exemplo`
                );

                window.open(`https://wa.me/55${numeroFormatado}?text=${mensagem}`, '_blank');
            }
        });
    }
});

// Configuração do mapa
let map;
let marker;

function initMap() {
    // Coordenadas iniciais (Brasil)
    const defaultLocation = { lat: -15.7801, lng: -47.9292 };

    // Criar mapa
    map = new google.maps.Map(document.getElementById('map'), {
        zoom: 4,
        center: defaultLocation,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true
    });

    // Criar marcador inicial (oculto)
    marker = new google.maps.Marker({
        map: map,
        draggable: true,
        visible: false
    });

    // Adicionar campo de busca
    const input = document.getElementById('endereco');
    const searchBox = new google.maps.places.SearchBox(input);

    // Atualizar mapa quando selecionar um lugar
    searchBox.addListener('places_changed', function() {
        const places = searchBox.getPlaces();

        if (places.length === 0) return;

        const place = places[0];
        if (!place.geometry || !place.geometry.location) return;

        // Atualizar mapa e marcador
        map.setCenter(place.geometry.location);
        map.setZoom(16);
        marker.setPosition(place.geometry.location);
        marker.setVisible(true);

        // Preencher campos de endereço
        preencherEndereco(place);
    });

    // Atualizar coordenadas quando o marcador for movido
    marker.addListener('dragend', function() {
        const position = marker.getPosition();
        atualizarCoordenadas(position.lat(), position.lng());
    });

    // Atualizar mapa quando o CEP for preenchido
    document.getElementById('cep').addEventListener('blur', function() {
        const cep = this.value.replace(/\D/g, '');
        if (cep.length === 8) {
            buscarCEP(cep);
        }
    });
}

function preencherEndereco(place) {
    // Limpar campos
    document.getElementById('logradouro').value = '';
    document.getElementById('numero').value = '';
    document.getElementById('bairro').value = '';
    document.getElementById('cidade').value = '';
    document.getElementById('estado').value = '';
    document.getElementById('cep').value = '';

    // Preencher campos com informações do lugar
    for (const component of place.address_components) {
        const type = component.types[0];

        switch (type) {
            case 'street_number':
                document.getElementById('numero').value = component.long_name;
                break;
            case 'route':
                document.getElementById('logradouro').value = component.long_name;
                break;
            case 'sublocality':
            case 'sublocality_level_1':
                document.getElementById('bairro').value = component.long_name;
                break;
            case 'administrative_area_level_2':
                document.getElementById('cidade').value = component.long_name;
                break;
            case 'administrative_area_level_1':
                document.getElementById('estado').value = component.short_name;
                break;
            case 'postal_code':
                document.getElementById('cep').value = component.long_name;
                break;
        }
    }

    // Atualizar coordenadas
    const position = place.geometry.location;
    atualizarCoordenadas(position.lat(), position.lng());
}

function atualizarCoordenadas(lat, lng) {
    document.getElementById('latitude').value = lat;
    document.getElementById('longitude').value = lng;
}

async function buscarCEP(cep) {
    try {
        const response = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
        const data = await response.json();

        if (!data.erro) {
            document.getElementById('logradouro').value = data.logradouro;
            document.getElementById('bairro').value = data.bairro;
            document.getElementById('cidade').value = data.localidade;
            document.getElementById('estado').value = data.uf;

            // Buscar coordenadas do endereço
            const geocoder = new google.maps.Geocoder();
            const endereco = `${data.logradouro}, ${data.localidade}, ${data.uf}, Brasil`;

            geocoder.geocode({ address: endereco }, function(results, status) {
                if (status === 'OK' && results[0]) {
                    const location = results[0].geometry.location;
                    
                    map.setCenter(location);
                    map.setZoom(16);
                    marker.setPosition(location);
                    marker.setVisible(true);

                    atualizarCoordenadas(location.lat(), location.lng());
                }
            });
        }
    } catch (error) {
        console.error('Erro ao buscar CEP:', error);
    }
} 