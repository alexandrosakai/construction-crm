class GeoLocalizador {
    static async obterLocalizacao() {
        try {
            const position = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject);
            });
            
            return {
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
                precisao: position.coords.accuracy
            };
        } catch (error) {
            console.error('Erro ao obter localização:', error);
            return null;
        }
    }

    static async registrarVisita(visitaContainer) {
        const localizacao = await this.obterLocalizacao();
        if (localizacao) {
            const localizacaoInput = document.createElement('input');
            localizacaoInput.type = 'hidden';
            localizacaoInput.name = 'localizacao';
            localizacaoInput.value = JSON.stringify(localizacao);
            visitaContainer.appendChild(localizacaoInput);
        }
    }
} 