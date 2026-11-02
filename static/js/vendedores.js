document.addEventListener('DOMContentLoaded', function() {
    const btnAdicionarVendedor = document.getElementById('adicionarVendedor');
    const vendedoresContainer = document.getElementById('vendedores-container');
    const MAX_VENDEDORES = 4;
    const btnFavorite = document.getElementById('btnFavorite');
    const starIcon = btnFavorite.querySelector('i');

    if (btnAdicionarVendedor && vendedoresContainer) {
        // Atualizar estado do botão inicialmente
        atualizarBotaoAdicionar();

        btnAdicionarVendedor.addEventListener('click', function() {
            if (getVendedoresAtuais().length >= MAX_VENDEDORES) {
                mostrarFeedback('Limite máximo de 4 vendedores atingido', 'warning');
                return;
            }

            // Criar novo vendedor
            const vendedorItem = document.createElement('div');
            vendedorItem.className = 'vendedor-item mb-3';
            
            // Criar options dos vendedores
            const vendedoresOptions = VENDEDORES.map(v => 
                `<option value="${v.value}">${v.nome}</option>`
            ).join('');

            vendedorItem.innerHTML = `
                <div class="d-flex align-items-center gap-2">
                    <select class="form-select form-select-sm vendedor-nome" required>
                        <option value="">Selecione o vendedor</option>
                        ${vendedoresOptions}
                    </select>
                    <button type="button" class="btn btn-danger btn-sm remover-vendedor">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;

            // Configurar select do vendedor
            const selectVendedor = vendedorItem.querySelector('.vendedor-nome');
            atualizarOpcoesDisponiveis(selectVendedor);
            
            // Configurar evento de seleção
            selectVendedor.addEventListener('change', function() {
                if (isVendedorDuplicado(this.value)) {
                    this.value = '';
                    mostrarFeedback('Este vendedor já está cadastrado', 'error');
                }
                atualizarTodasOpcoes();
            });

            // Configurar botão de remover
            const btnRemover = vendedorItem.querySelector('.remover-vendedor');
            btnRemover.addEventListener('click', function() {
                if(confirm('Tem certeza que deseja remover este vendedor?')) {
                    vendedorItem.remove();
                    atualizarBotaoAdicionar();
                    atualizarTodasOpcoes();
                }
            });

            // Adicionar ao container
            vendedoresContainer.appendChild(vendedorItem);
            atualizarBotaoAdicionar();
        });
    }

    function getVendedoresAtuais() {
        return Array.from(vendedoresContainer.querySelectorAll('.vendedor-nome'))
            .map(select => select.value)
            .filter(Boolean);
    }

    function isVendedorDuplicado(valor) {
        if (!valor) return false;
        const vendedores = getVendedoresAtuais();
        return vendedores.filter(v => v === valor).length > 1;
    }

    function atualizarBotaoAdicionar() {
        const vendedoresAtuais = getVendedoresAtuais();
        btnAdicionarVendedor.disabled = vendedoresAtuais.length >= MAX_VENDEDORES;
        
        // Atualizar contador
        const contador = document.getElementById('vendedoresContador') || criarContador();
        contador.textContent = `${vendedoresAtuais.length}/${MAX_VENDEDORES} vendedores`;
        
        if (vendedoresAtuais.length >= MAX_VENDEDORES) {
            contador.classList.add('text-danger');
        } else {
            contador.classList.remove('text-danger');
        }
    }

    function criarContador() {
        const contador = document.createElement('small');
        contador.id = 'vendedoresContador';
        contador.className = 'ms-2 text-muted';
        btnAdicionarVendedor.parentNode.appendChild(contador);
        return contador;
    }

    function atualizarOpcoesDisponiveis(selectAtual) {
        const vendedoresSelecionados = Array.from(vendedoresContainer.querySelectorAll('.vendedor-nome'))
            .map(select => select.value)
            .filter(Boolean);

        Array.from(selectAtual.options).forEach(option => {
            if (option.value) {
                option.disabled = vendedoresSelecionados.includes(option.value) && 
                                selectAtual.value !== option.value;
            }
        });
    }

    function atualizarTodasOpcoes() {
        const todosSelects = vendedoresContainer.querySelectorAll('.vendedor-nome');
        todosSelects.forEach(select => atualizarOpcoesDisponiveis(select));
    }

    function mostrarFeedback(mensagem, tipo) {
        const feedbackDiv = document.createElement('div');
        feedbackDiv.className = `alert alert-${tipo} alert-dismissible fade show`;
        feedbackDiv.role = 'alert';
        feedbackDiv.innerHTML = `
            ${mensagem}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        vendedoresContainer.insertAdjacentElement('beforebegin', feedbackDiv);
        
        setTimeout(() => {
            feedbackDiv.remove();
        }, 3000);
    }

    // Verificar se a obra está favoritada no localStorage
    function checkFavoriteStatus(obraId) {
        const favorites = JSON.parse(localStorage.getItem('obrasFavoritas') || '[]');
        return favorites.includes(obraId);
    }
    
    // Atualizar visual da estrela
    function updateStarVisual(isFavorite) {
        if (isFavorite) {
            starIcon.classList.remove('far');
            starIcon.classList.add('fas');
            btnFavorite.title = 'Remover dos favoritos';
        } else {
            starIcon.classList.remove('fas');
            starIcon.classList.add('far');
            btnFavorite.title = 'Adicionar aos favoritos';
        }
    }
    
    // Alternar status de favorito
    function toggleFavorite(obraId) {
        const favorites = JSON.parse(localStorage.getItem('obrasFavoritas') || '[]');
        const index = favorites.indexOf(obraId);
        
        if (index === -1) {
            // Adicionar aos favoritos
            favorites.push(obraId);
            updateStarVisual(true);
        } else {
            // Remover dos favoritos
            favorites.splice(index, 1);
            updateStarVisual(false);
        }
        
        localStorage.setItem('obrasFavoritas', JSON.stringify(favorites));
    }
    
    // Evento de clique no botão de favorito
    btnFavorite.addEventListener('click', function() {
        const numeroObra = document.getElementById('numeroObra').value;
        
        if (!numeroObra) {
            alert('Por favor, insira um número de obra primeiro.');
            return;
        }
        
        toggleFavorite(numeroObra);
        
        // Animação de feedback
        starIcon.classList.add('animate__animated', 'animate__bounceIn');
        setTimeout(() => {
            starIcon.classList.remove('animate__animated', 'animate__bounceIn');
        }, 1000);
    });
    
    // Atualizar estrela quando carregar uma obra
    function atualizarEstrelaAoCarregarObra(numeroObra) {
        if (numeroObra) {
            const isFavorite = checkFavoriteStatus(numeroObra);
            updateStarVisual(isFavorite);
        } else {
            updateStarVisual(false);
        }
    }
    
    // Observar mudanças no campo número da obra
    const numeroObraInput = document.getElementById('numeroObra');
    numeroObraInput.addEventListener('change', function() {
        atualizarEstrelaAoCarregarObra(this.value);
    });
    
    // Inicialização
    atualizarEstrelaAoCarregarObra(numeroObraInput.value);

    // Atualizar a função de compartilhar via WhatsApp
    function compartilharViaWhatsApp(telefone, mensagem, especialidade) {
        // Formatar o telefone (remover caracteres não numéricos)
        const numeroLimpo = telefone.replace(/\D/g, '');
        
        // Verificar se o número tem o formato correto
        if (numeroLimpo.length < 10 || numeroLimpo.length > 11) {
            alert('Número de telefone inválido');
            return;
        }
        
        // Mensagem personalizada para pintores
        if (especialidade?.toLowerCase() === 'pintor') {
            mensagem = `Olá ${nome}, Pintor!

Tudo bem?

Agradecemos por compartilhar seu número conosco! Queremos fortalecer essa parceria e, para isso, criamos um grupo exclusivo no WhatsApp @https://chat.whatsapp.com/Ezh8wcyh05kIkLmURYNLFA onde você terá acesso às principais novidades, lançamentos e ofertas diárias. Além disso, você ainda poderá concorrer a prêmios incríveis!

Atenciosamente,
Empresa Exemplo`;
        }
        
        // Formatar mensagem (codificar para URL)
        const mensagemFormatada = encodeURIComponent(mensagem);
        
        // Criar link do WhatsApp
        const linkWhatsApp = `https://wa.me/55${numeroLimpo}?text=${mensagemFormatada}`;
        
        // Abrir em nova aba
        window.open(linkWhatsApp, '_blank');
    }

    // Atualizar o evento do botão WhatsApp
    const btnWhatsApp = document.getElementById('compartilharWhatsApp');
    const inputTelefone = document.getElementById('telefone');
    
    if (btnWhatsApp && inputTelefone) {
        btnWhatsApp.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Obter dados do formulário
            const nome = document.getElementById('nome')?.value || '';
            const cargo = document.getElementById('cargo')?.value || '';
            const telefone = inputTelefone.value;
            
            // Criar mensagem personalizada
            const mensagem = `Olá ${nome}, 
Sou do Empresa Exemplo e gostaria de conversar sobre uma parceria.

Você trabalha como ${cargo}, correto?

Podemos conversar?`;
            
            compartilharViaWhatsApp(telefone, mensagem, cargo);
        });
        
        // Habilitar/desabilitar botão baseado no telefone
        inputTelefone.addEventListener('input', function() {
            const numeroLimpo = this.value.replace(/\D/g, '');
            btnWhatsApp.disabled = numeroLimpo.length < 10;
        });
    }
}); 