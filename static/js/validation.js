// Validação em tempo real
class FormValidator {
  static rules = {
    telefone: /^\(\d{2}\) \d{4,5}-\d{4}$/,
    email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
    cep: /^\d{5}-?\d{3}$/,
    cpf: /^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$/
  };

  static messages = {
    telefone: 'Formato: (99) 99999-9999',
    email: 'Digite um email válido',
    cep: 'CEP inválido',
    cpf: 'CPF inválido'
  };

  static validateField(field, value) {
    const rule = this.rules[field];
    if (!rule) return true;

    const isValid = rule.test(value);
    const element = document.getElementById(field);
    
    if (element) {
      element.classList.toggle('is-invalid', !isValid);
      const feedback = element.nextElementSibling;
      if (feedback && feedback.classList.contains('invalid-feedback')) {
        feedback.textContent = isValid ? '' : this.messages[field];
      }
    }

    return isValid;
  }

  static validateForm(formElement) {
    let isValid = true;
    const fields = formElement.querySelectorAll('input, select, textarea');
    
    fields.forEach(field => {
      if (field.id && this.rules[field.id]) {
        isValid = this.validateField(field.id, field.value) && isValid;
      }
    });

    return isValid;
  }
}

// Adicionar listeners para validação em tempo real
document.querySelectorAll('input, select, textarea').forEach(field => {
  field.addEventListener('input', () => {
    if (field.id) {
      FormValidator.validateField(field.id, field.value);
    }
  });
}); 