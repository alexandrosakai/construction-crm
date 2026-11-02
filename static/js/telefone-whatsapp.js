document.addEventListener('DOMContentLoaded', function() {
    // Função para aplicar máscara ao telefone
    function aplicarMascaraTelefone(input) {
        let valor = input.value.replace(/\D/g, ''); // Remove tudo que não é número
        
        // Limita a 11 dígitos
        valor = valor.substring(0, 11);
        
        // Aplica a máscara
        if (valor.length <= 10) {
            // Formato (00) 0000-0000
            valor = valor.replace(/^(\d{2})(\d{4})(\d{4}).*/, '($1) $2-$3');
        } else {
            // Formato (00) 00000-0000
            valor = valor.replace(/^(\d{2})(\d{5})(\d{4}).*/, '($1) $2-$3');
        }
        
        input.value = valor;
        
        // Habilita/desabilita botão do WhatsApp
        const whatsappBtn = input.parentElement.querySelector('.whatsapp-btn');
        if (whatsappBtn) {
            whatsappBtn.style.display = 'flex'; // Garante que o botão está visível
            whatsappBtn.disabled = !validarTelefone(valor);
        }
        
        return valor;
    }
    
    // Função para validar número de telefone
    function validarTelefone(telefone) {
        const numero = telefone.replace(/\D/g, '');
        return numero.length >= 10 && numero.length <= 11;
    }
    
    // Função para abrir WhatsApp com mensagem
    function abrirWhatsAppComMensagem(numero, nome, especialidade, isProfissional = false) {
        numero = numero.replace(/\D/g, '');
        if (numero.length === 10) {
            numero = numero.substring(0, 2) + '9' + numero.substring(2);
        }
        
        let mensagem;
        if (isProfissional) {
            // Mensagem para profissionais
            mensagem = encodeURIComponent(
                `Olá ${nome} ${especialidade},\n\n` +
                `Tudo bem?\n\n` +
                `Agradecemos por compartilhar seu número conosco! Queremos fortalecer essa parceria e, para isso, criamos um grupo exclusivo no WhatsApp onde você terá acesso às principais novidades, lançamentos e ofertas diárias. Além disso, você ainda poderá concorrer a prêmios incríveis!\n\n` +
                `👉 Clique aqui para entrar no grupo: https://chat.whatsapp.com/${especialidade}\n\n` +
                `Não perca essa oportunidade de ficar por dentro de tudo que preparamos especialmente para você. Esperamos você por lá!\n\n` +
                `Grande abraço,\n\n` +
                `Prospecção Empresa Exemplo\n` +
                `(11) 90000-0000`
            );
        } else {
            // Mensagem para clientes
            const endereco = `${document.getElementById('logradouro').value}, ${document.getElementById('numero').value}`;
            const bairro = document.getElementById('bairro').value;
            const cidade = document.getElementById('cidade').value;
            
            mensagem = encodeURIComponent(
                `Olá ${nome},\n\n` +
                `Tudo bem? Espero que sim!\n\n` +
                `Passei na sua Obra na ${endereco} no ${bairro} em ${cidade}, gostaria de te apresentar o Empresa Exemplo que está a mais de 39 anos em Gurupi, uma referência em materiais de construção e soluções para obras de todos os portes. Seja para reformas, construções ou projetos personalizados, temos tudo o que você precisa com qualidade e preço justo. Podemos te atender em todas as Etapas da sua Obra.\n\n` +
                `Para facilitar o seu acesso às nossas ofertas e novidades, que tal fazer um cadastro rápido? É simples, prático e você já começa a aproveitar vantagens exclusivas!\n\n` +
                `👉 Clique aqui para se cadastrar: www.example.com/cadastro\n\n` +
                `Se precisar de ajuda ou tiver alguma dúvida, estou à disposição para te auxiliar. Vamos transformar a sua obra em um sucesso!\n\n` +
                `Atenciosamente,\n` +
                `Admin\n` +
                `Prospecção\n` +
                `[Seu Contato]`
            );
        }
        
        const url = `https://wa.me/55${numero}?text=${mensagem}`;
        window.open(url, '_blank');
    }
    
    // Adiciona a função ao objeto window para acesso global
    window.abrirWhatsAppComMensagem = abrirWhatsAppComMensagem;
    
    // Função para configurar o botão do WhatsApp
    function configurarBotaoWhatsApp(input, whatsappBtn) {
        if (!whatsappBtn) return;

        whatsappBtn.style.display = 'flex';
        
        whatsappBtn.addEventListener('click', function() {
            const numero = input.value;
            const profissionalContainer = input.closest('.card-body');
            
            if (validarTelefone(numero)) {
                // Se for um profissional (verificando se está na seção de profissionais)
                if (profissionalContainer && profissionalContainer.querySelector('.profissional-nome')) {
                    const nome = profissionalContainer.querySelector('.profissional-nome').value;
                    const especialidadeSelect = profissionalContainer.querySelector('.profissional-especialidade');
                    const especialidade = especialidadeSelect.options[especialidadeSelect.selectedIndex].text;
                    abrirWhatsAppComMensagem(numero, nome, especialidade, true);
                } else {
                    // Se for um cliente
                    const nome = document.getElementById('nome').value;
                    abrirWhatsAppComMensagem(numero, nome, '', false);
                }
            }
        });
    }

    // Aplicar máscara e configurar WhatsApp para todos os campos de telefone
    function configurarCampoTelefone(input) {
        const whatsappBtn = input.parentElement.querySelector('.whatsapp-btn');
        
        input.addEventListener('input', function() {
            const valor = aplicarMascaraTelefone(this);
            if (whatsappBtn) {
                whatsappBtn.disabled = !validarTelefone(valor);
            }
        });
        
        input.addEventListener('blur', function() {
            if (!validarTelefone(this.value)) {
                this.classList.add('is-invalid');
            } else {
                this.classList.remove('is-invalid');
            }
        });
        
        if (whatsappBtn) {
            configurarBotaoWhatsApp(input, whatsappBtn);
        }
    }

    // Configurar campos de telefone existentes
    document.querySelectorAll('.telefone-mask').forEach(configurarCampoTelefone);

    // Observar novos campos de telefone adicionados dinamicamente
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1) { // ELEMENT_NODE
                    const newInputs = node.querySelectorAll('.telefone-mask');
                    newInputs.forEach(configurarCampoTelefone);
                }
            });
        });
    });

    // Observar alterações no container de profissionais
    const profissionaisContainer = document.getElementById('profissionais-container');
    if (profissionaisContainer) {
        observer.observe(profissionaisContainer, { childList: true, subtree: true });
    }
}); 