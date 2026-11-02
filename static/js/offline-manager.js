class OfflineManager {
    constructor() {
        this.db = new Dexie('ObraOfflineDB');
        this.setupDatabase();
        this.setupEventListeners();
    }

    setupDatabase() {
        this.db.version(1).stores({
            obras: '++id,numero,dados,status',
            fotos: '++id,obraId,etapaId,dados',
            sync: '++id,tipo,dados,timestamp'
        });
    }

    setupEventListeners() {
        window.addEventListener('online', () => this.sincronizar());
        window.addEventListener('offline', () => this.ativarModoOffline());
    }

    async salvarOffline(dados) {
        try {
            await this.db.obras.add({
                dados,
                status: 'pending',
                timestamp: Date.now()
            });
        } catch (error) {
            console.error('Erro ao salvar offline:', error);
        }
    }
} 