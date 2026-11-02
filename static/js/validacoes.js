// Máscara e validação de CPF
document.addEventListener('DOMContentLoaded', function() {
    const cpfInput = document.getElementById('cpf');
    
    cpfInput.addEventListener('input', function(e) {
        let value = e.target.value.replace(/\D/g, '');
        if (value.length > 11) value = value.slice(0, 11);
        
        if (value.length > 9) {
            value = value.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, '$1.$2.$3-$4');
        } else if (value.length > 6) {
            value = value.replace(/^(\d{3})(\d{3})(\d{3})/, '$1.$2.$3');
        } else if (value.length > 3) {
            value = value.replace(/^(\d{3})(\d{3})/, '$1.$2');
        }
        
        e.target.value = value;
    });
});

// Validação de datas
function validarDatas() {
    const dataInicio = document.getElementById('dataInicio');
    const dataTermino = document.getElementById('dataTermino');
    
    dataTermino.addEventListener('change', function() {
        if (dataInicio.value && this.value) {
            if (new Date(this.value) < new Date(dataInicio.value)) {
                this.setCustomValidity('A data de término não pode ser anterior à data de início');
                this.reportValidity();
            } else {
                this.setCustomValidity('');
            }
        }
    });
}

// Validação de metragem
function validarMetragem() {
    const metragemInput = document.getElementById('metragem');
    
    metragemInput.addEventListener('input', function() {
        if (this.value < 10) {
            this.setCustomValidity('A metragem mínima é de 10m²');
            this.reportValidity();
        } else {
            this.setCustomValidity('');
        }
    });
} 