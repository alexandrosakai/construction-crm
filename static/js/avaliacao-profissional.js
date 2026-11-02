class AvaliacaoProfissional {
    static adicionarAvaliacao(container) {
        const avaliacaoHTML = `
            <div class="rating mt-2">
                <span class="star" data-rating="1"><i class="far fa-star"></i></span>
                <span class="star" data-rating="2"><i class="far fa-star"></i></span>
                <span class="star" data-rating="3"><i class="far fa-star"></i></span>
                <span class="star" data-rating="4"><i class="far fa-star"></i></span>
                <span class="star" data-rating="5"><i class="far fa-star"></i></span>
            </div>
        `;
        
        container.insertAdjacentHTML('beforeend', avaliacaoHTML);
        this.setupEventos(container);
    }

    static setupEventos(container) {
        const stars = container.querySelectorAll('.star');
        stars.forEach(star => {
            star.addEventListener('click', function() {
                const rating = this.dataset.rating;
                stars.forEach(s => {
                    const starRating = s.dataset.rating;
                    s.querySelector('i').className = 
                        starRating <= rating ? 'fas fa-star' : 'far fa-star';
                });
            });
        });
    }
} 