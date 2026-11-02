class FotoHandler {
    static async previewFoto(input, previewContainer) {
        if (input.files && input.files[0]) {
            const reader = new FileReader();
            
            reader.onload = function(e) {
                const preview = document.createElement('div');
                preview.className = 'foto-preview';
                preview.innerHTML = `
                    <img src="${e.target.result}" class="img-thumbnail">
                    <button type="button" class="btn btn-sm btn-danger remove-foto">
                        <i class="fas fa-times"></i>
                    </button>
                `;
                
                previewContainer.appendChild(preview);
            };
            
            reader.readAsDataURL(input.files[0]);
        }
    }
}

// Galeria de fotos por etapa
class GaleriaEtapa {
    constructor(etapaContainer) {
        this.container = etapaContainer;
        this.setupGaleria();
    }

    setupGaleria() {
        const galeriaHTML = `
            <div class="galeria-fotos mt-3">
                <div class="row g-2 foto-previews"></div>
                <div class="progress mt-2 d-none">
                    <div class="progress-bar" role="progressbar"></div>
                </div>
            </div>
        `;
        
        this.container.insertAdjacentHTML('beforeend', galeriaHTML);
    }
} 