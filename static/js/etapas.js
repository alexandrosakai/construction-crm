document.addEventListener('DOMContentLoaded', function() {
    // Elementos do DOM
    const btnAdicionarEtapa = document.getElementById('adicionarEtapa');
    const etapasContainer = document.getElementById('etapas-container');
    
    if (!btnAdicionarEtapa || !etapasContainer) {
        console.error('Elementos necessários não encontrados');
        return;
    }

    // Adicionar nova etapa
    btnAdicionarEtapa.addEventListener('click', function() {
        const novaEtapa = document.createElement('div');
        novaEtapa.className = 'etapa-item border rounded p-3 mb-3';
        novaEtapa.innerHTML = `
            <div class="row">
                <div class="col-md-4 mb-3">
                    <label class="form-label">Data Prevista</label>
                    <input type="date" class="form-control etapa-data" required>
                </div>
                <div class="col-md-4 mb-3">
                    <label class="form-label">Tipo da Etapa</label>
                    <select class="form-select etapa-tipo" required>
                        <option value="">Selecione</option>
                        <option value="projeto">Elaboração de Projeto</option>
                        <option value="preliminares">Serviços Preliminares</option>
                        <option value="fundacao">Fundação</option>
                        <option value="estrutura">Estrutura</option>
                        <option value="alvenaria">Alvenaria</option>
                        <option value="vedacoes">Vedações</option>
                        <option value="cobertura">Cobertura</option>
                        <option value="impermeabilizacao">Impermeabilização</option>
                        <option value="instalacoes_hidraulicas">Instalações Hidráulicas</option>
                        <option value="instalacoes_eletricas">Instalações Elétricas</option>
                        <option value="revestimentos">Revestimentos</option>
                        <option value="pintura">Pintura</option>
                        <option value="acabamentos">Acabamentos</option>
                    </select>
                </div>
                <div class="col-md-3 mb-3">
                    <label class="form-label">Status</label>
                    <select class="form-select etapa-status" required>
                        <option value="">Selecione</option>
                        <option value="nao_iniciada">Não Iniciada</option>
                        <option value="em_andamento">Em Andamento</option>
                        <option value="concluida">Concluída</option>
                        <option value="atrasada">Atrasada</option>
                        <option value="pausada">Pausada</option>
                    </select>
                </div>
                <div class="col-md-1 mb-3">
                    <label class="form-label d-block">&nbsp;</label>
                    <button type="button" class="btn btn-danger remover-etapa">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>

            <!-- Campo de fotos -->
            <div class="row mt-3">
                <div class="col-12 mb-3">
                    <label class="form-label">Fotos da Etapa</label>
                    <input type="file" class="form-control etapa-fotos" multiple accept="image/*">
                    <div class="galeria-fotos mt-2 d-flex flex-wrap gap-2">
                        <!-- As miniaturas serão adicionadas aqui -->
                    </div>
                </div>
            </div>

            <!-- Fornecedores -->
            <div class="fornecedores-container">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h6 class="mb-0">Fornecedores</h6>
                    <button type="button" class="btn btn-success btn-sm adicionar-fornecedor">
                        <i class="fas fa-plus"></i> Adicionar Fornecedor
                    </button>
                </div>
                <div class="lista-fornecedores">
                    <!-- Os fornecedores serão adicionados aqui -->
                </div>
            </div>
        `;

        // Configurar preview de imagens
        const inputFotos = novaEtapa.querySelector('.etapa-fotos');
        const galeriaFotos = novaEtapa.querySelector('.galeria-fotos');
        
        inputFotos.addEventListener('change', function(e) {
            const files = Array.from(e.target.files);
            
            files.forEach(file => {
                if (file.type.startsWith('image/')) {
                    const miniaturaContainer = document.createElement('div');
                    miniaturaContainer.className = 'miniatura-container position-relative';
                    miniaturaContainer.style.width = '150px';
                    
                    const img = document.createElement('img');
                    img.className = 'img-fluid rounded';
                    img.file = file;
                    
                    const btnRemover = document.createElement('button');
                    btnRemover.className = 'btn btn-danger btn-sm position-absolute top-0 end-0 m-1';
                    btnRemover.innerHTML = '<i class="fas fa-times"></i>';
                    btnRemover.onclick = function() {
                        if(confirm('Remover esta foto?')) {
                            miniaturaContainer.remove();
                            // Atualizar o FileList do input
                            const dt = new DataTransfer();
                            const { files } = inputFotos;
                            for (let i = 0; i < files.length; i++) {
                                const file = files[i];
                                if (file !== img.file) {
                                    dt.items.add(file);
                                }
                            }
                            inputFotos.files = dt.files;
                        }
                    };
                    
                    miniaturaContainer.appendChild(img);
                    miniaturaContainer.appendChild(btnRemover);
                    galeriaFotos.appendChild(miniaturaContainer);
                    
                    const reader = new FileReader();
                    reader.onload = (function(aImg) { 
                        return function(e) { 
                            aImg.src = e.target.result; 
                        }; 
                    })(img);
                    reader.readAsDataURL(file);
                }
            });
        });

        // Configurar adição de fornecedores
        const btnAddFornecedor = novaEtapa.querySelector('.adicionar-fornecedor');
        const listaFornecedores = novaEtapa.querySelector('.lista-fornecedores');

        btnAddFornecedor.addEventListener('click', function() {
            const fornecedorItem = document.createElement('div');
            fornecedorItem.className = 'fornecedor-item border rounded p-2 mb-2';
            fornecedorItem.innerHTML = `
                <div class="d-flex gap-2">
                    <div class="flex-grow-1">
                        <input type="text" class="form-control form-control-sm" placeholder="Nome do fornecedor" required>
                    </div>
                    <div class="flex-grow-1">
                        <select class="form-select form-select-sm" required>
                            <option value="">Selecione o material</option>
                            <option value="areia">Areia</option>
                            <option value="brita">Brita</option>
                            <option value="cimento">Cimento</option>
                            <option value="tijolo">Tijolo</option>
                            <option value="telha">Telha</option>
                            <option value="ferro">Ferro</option>
                            <option value="tubo_pvc">Tubo PVC</option>
                            <option value="fio_eletrico">Fio Elétrico</option>
                            <option value="tinta">Tinta</option>
                            <option value="piso">Piso</option>
                            <option value="argamassa">Argamassa</option>
                            <option value="porta">Porta</option>
                            <option value="janela">Janela</option>
                            <option value="vaso_sanitario">Vaso Sanitário</option>
                            <option value="pia">Pia</option>
                            <option value="torneira">Torneira</option>
                            <option value="chuveiro">Chuveiro</option>
                            <option value="madeira">Madeira</option>
                            <option value="vidro">Vidro</option>
                        </select>
                    </div>
                    <button type="button" class="btn btn-danger btn-sm remover-fornecedor">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;

            // Configurar remoção do fornecedor
            const btnRemoverFornecedor = fornecedorItem.querySelector('.remover-fornecedor');
            btnRemoverFornecedor.addEventListener('click', function() {
                if(confirm('Tem certeza que deseja remover este fornecedor?')) {
                    fornecedorItem.remove();
                }
            });

            listaFornecedores.appendChild(fornecedorItem);
            fornecedorItem.querySelector('input').focus();
        });

        // Configurar remoção da etapa
        const btnRemover = novaEtapa.querySelector('.remover-etapa');
        btnRemover.addEventListener('click', function() {
            if(confirm('Tem certeza que deseja remover esta etapa?')) {
                novaEtapa.remove();
            }
        });

        etapasContainer.appendChild(novaEtapa);
    });

    // Função auxiliar para configurar fornecedores
    function configurarFornecedores(etapaItem) {
        // ... código existente para fornecedores ...
    }
}); 