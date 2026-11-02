document.addEventListener('DOMContentLoaded', function() {
    const btnAdicionarProfissional = document.getElementById('adicionarProfissional');
    const profissionaisCard = document.querySelector('.card-body');
    
    // Remover o código que remove o primeiro profissional
    // const primeiroProfissional = profissionaisCard.querySelector('.row');
    // if (primeiroProfissional) {
    //     primeiroProfissional.remove();
    // }

    btnAdicionarProfissional.addEventListener('click', function() {
        const cardProfissional = this.closest('.card').querySelector('.card-body');
        const isFirstProfessional = !cardProfissional.querySelector('.row');
        
        const novaRow = document.createElement('div');
        novaRow.className = 'row' + (isFirstProfessional ? '' : ' border-top pt-3 mt-3');
        novaRow.innerHTML = `
            <div class="col-md-4 mb-2">
                <label class="form-label small">Nome do Profissional</label>
                <div class="d-flex align-items-center gap-2">
                    <input type="text" class="form-control form-control-sm profissional-nome" required 
                           placeholder="Digite o nome completo">
                    <div class="avaliacao-estrelas">
                        <i class="far fa-star" data-rating="1"></i>
                        <i class="far fa-star" data-rating="2"></i>
                        <i class="far fa-star" data-rating="3"></i>
                        <i class="far fa-star" data-rating="4"></i>
                        <i class="far fa-star" data-rating="5"></i>
                        <input type="hidden" class="rating-value" value="0">
                    </div>
                    <button type="button" class="btn btn-danger btn-sm">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
            <div class="col-md-4 mb-2">
                <label class="form-label small">Especialidade</label>
                <select class="form-select form-select-sm profissional-especialidade" required>
                    <option value="">Selecione</option>
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
                </select>
            </div>
            <div class="col-md-4 mb-2">
                <label class="form-label small">Telefone</label>
                <div class="input-group input-group-sm">
                    <input type="tel" class="form-control telefone-mask profissional-telefone" 
                           placeholder="(00) 00000-0000" required>
                    <button class="btn btn-success whatsapp-btn" type="button" disabled style="width: 40px;">
                        <i class="fab fa-whatsapp"></i>
                    </button>
                </div>
            </div>
        `;

        // Configurar avaliação por estrelas
        const estrelas = novaRow.querySelector('.avaliacao-estrelas');
        configurarEstrelas(estrelas);

        // Configurar botão de excluir
        const btnExcluir = novaRow.querySelector('.btn-danger');
        btnExcluir.onclick = function() {
            if(confirm('Tem certeza que deseja excluir este profissional?')) {
                novaRow.remove();
            }
        };

        // Configurar WhatsApp
        const telefoneInput = novaRow.querySelector('.profissional-telefone');
        const whatsappBtn = novaRow.querySelector('.whatsapp-btn');
        const nomeInput = novaRow.querySelector('.profissional-nome');
        const especialidadeSelect = novaRow.querySelector('.profissional-especialidade');

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

        cardProfissional.appendChild(novaRow);
    });

    // Função para configurar estrelas
    function configurarEstrelas(container) {
        const estrelas = container.querySelectorAll('i');
        const ratingInput = container.querySelector('.rating-value');

        estrelas.forEach(estrela => {
            // Hover effect
            estrela.addEventListener('mouseover', function() {
                const rating = this.dataset.rating;
                highlightStars(estrelas, rating);
            });

            // Mouse leave
            estrela.addEventListener('mouseleave', function() {
                const rating = ratingInput.value;
                highlightStars(estrelas, rating);
            });

            // Click
            estrela.addEventListener('click', function() {
                const rating = this.dataset.rating;
                ratingInput.value = rating;
                highlightStars(estrelas, rating);
            });
        });
    }

    // Função para destacar estrelas
    function highlightStars(estrelas, rating) {
        estrelas.forEach(estrela => {
            const starRating = estrela.dataset.rating;
            estrela.className = starRating <= rating ? 'fas fa-star text-warning' : 'far fa-star';
        });
    }
}); 