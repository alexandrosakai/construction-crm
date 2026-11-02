document.addEventListener('DOMContentLoaded', function() {
    // Elementos do DOM
    const btnAdicionarEtapa = document.getElementById('adicionarEtapa');
    const btnNovaVisita = document.getElementById('novaVisita');
    const etapasContainer = document.getElementById('etapas-container');
    const visitasContainer = document.getElementById('visitas-container');
    const templateEtapa = document.getElementById('template-etapa');
    const templateVisita = document.getElementById('template-visita');

    if (!btnAdicionarEtapa || !etapasContainer || !templateEtapa) {
        console.error('Elementos necessários não encontrados');
        return;
    }

    // Adicionar nova etapa
    btnAdicionarEtapa.addEventListener('click', function() {
        const novaEtapa = templateEtapa.content.cloneNode(true);
        const etapaItem = novaEtapa.querySelector('.etapa-item');
        
        // Configurar evento de remoção
        const btnRemover = novaEtapa.querySelector('.remover-etapa');
        if (btnRemover) {
            btnRemover.addEventListener('click', function(e) {
                if(confirm('Tem certeza que deseja remover esta etapa?')) {
                    e.target.closest('.etapa-item').remove();
                }
            });
        }

        // Configurar preview de imagens para etapa
        const inputFotos = novaEtapa.querySelector('.etapa-fotos');
        const galeriaFotos = novaEtapa.querySelector('.galeria-fotos');
        
        inputFotos.addEventListener('change', function(e) {
            const files = Array.from(e.target.files);
            
            files.forEach(file => {
                if (file.type.startsWith('image/')) {
                    // Criar container para miniatura
                    const miniaturaContainer = document.createElement('div');
                    miniaturaContainer.className = 'miniatura-container';
                    
                    // Criar imagem miniatura
                    const img = document.createElement('img');
                    img.file = file;
                    
                    // Criar botão de remover
                    const btnRemover = document.createElement('button');
                    btnRemover.className = 'remover-foto';
                    btnRemover.innerHTML = '<i class="fas fa-times"></i>';
                    btnRemover.addEventListener('click', function() {
                        if(confirm('Remover esta foto?')) {
                            miniaturaContainer.remove();
                            // Atualizar o FileList do input
                            atualizarInputFiles(inputFotos, file);
                        }
                    });
                    
                    // Adicionar elementos ao container
                    miniaturaContainer.appendChild(img);
                    miniaturaContainer.appendChild(btnRemover);
                    galeriaFotos.appendChild(miniaturaContainer);
                    
                    // Criar preview da imagem
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

        // Configurar materiais
        configurarMateriais(etapaItem);

        etapasContainer.appendChild(novaEtapa);
    });

    // Adicionar nova visita
    btnNovaVisita.addEventListener('click', function() {
        const novaVisita = templateVisita.content.cloneNode(true);
        
        // Configurar evento de remoção da visita
        novaVisita.querySelector('.remover-visita').addEventListener('click', function(e) {
            if(confirm('Tem certeza que deseja remover esta visita?')) {
                e.target.closest('.visita-item').remove();
            }
        });

        // Configurar preview de imagens
        const inputFotos = novaVisita.querySelector('.visita-fotos');
        const galeriaFotos = novaVisita.querySelector('.galeria-fotos');
        
        inputFotos.addEventListener('change', function(e) {
            const files = Array.from(e.target.files);
            
            files.forEach(file => {
                if (file.type.startsWith('image/')) {
                    // Criar container para miniatura
                    const miniaturaContainer = document.createElement('div');
                    miniaturaContainer.className = 'miniatura-container';
                    
                    // Criar imagem miniatura
                    const img = document.createElement('img');
                    img.file = file;
                    
                    // Criar botão de remover
                    const btnRemover = document.createElement('button');
                    btnRemover.className = 'remover-foto';
                    btnRemover.innerHTML = '<i class="fas fa-times"></i>';
                    btnRemover.addEventListener('click', function() {
                        if(confirm('Remover esta foto?')) {
                            miniaturaContainer.remove();
                            // Atualizar o FileList do input
                            atualizarInputFiles(inputFotos, file);
                        }
                    });
                    
                    // Adicionar elementos ao container
                    miniaturaContainer.appendChild(img);
                    miniaturaContainer.appendChild(btnRemover);
                    galeriaFotos.appendChild(miniaturaContainer);
                    
                    // Criar preview da imagem
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

        visitasContainer.appendChild(novaVisita);
    });
    
    // Função para atualizar o FileList do input após remover uma foto
    function atualizarInputFiles(inputElement, fileToRemove) {
        const dt = new DataTransfer();
        const { files } = inputElement;
        
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            if (file !== fileToRemove) {
                dt.items.add(file);
            }
        }
        
        inputElement.files = dt.files;
    }

    // Função para configurar materiais
    function configurarMateriais(etapaItem) {
        const btnAdicionar = etapaItem.querySelector('.adicionar-material');
        const listaMateriais = etapaItem.querySelector('.lista-materiais');
        const inputMaterial = etapaItem.querySelector('.etapa-material');
        const inputQuantidade = etapaItem.querySelector('.etapa-quantidade');
        const selectUnidade = etapaItem.querySelector('.etapa-unidade');

        if (!btnAdicionar || !listaMateriais || !inputMaterial || !inputQuantidade || !selectUnidade) {
            console.error('Elementos de materiais não encontrados');
            return;
        }

        btnAdicionar.addEventListener('click', function() {
            adicionarMaterial();
        });

        // Adicionar evento de tecla Enter
        inputMaterial.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                if (inputQuantidade.value) {
                    adicionarMaterial();
                } else {
                    inputQuantidade.focus();
                }
            }
        });

        inputQuantidade.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                adicionarMaterial();
            }
        });

        function adicionarMaterial() {
            const material = inputMaterial.value.trim();
            const quantidade = inputQuantidade.value;
            const unidade = selectUnidade.value;

            if (material && quantidade) {
                const materialItem = document.createElement('div');
                materialItem.className = 'material-item d-flex align-items-center mb-2';
                materialItem.innerHTML = `
                    <span class="flex-grow-1">${material} - ${quantidade} ${unidade}</span>
                    <button type="button" class="btn btn-sm btn-danger ms-2 remover-material">
                        <i class="fas fa-times"></i>
                    </button>
                `;

                materialItem.querySelector('.remover-material').addEventListener('click', function() {
                    if(confirm('Tem certeza que deseja remover este material?')) {
                        materialItem.remove();
                    }
                });

                listaMateriais.appendChild(materialItem);
                
                // Limpar campos
                inputMaterial.value = '';
                inputQuantidade.value = '';
                inputMaterial.focus();
            } else {
                alert('Por favor, preencha o material e a quantidade');
            }
        }
    }
}); 