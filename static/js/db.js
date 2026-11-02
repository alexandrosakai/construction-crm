// Banco de dados local usando IndexedDB
const db = new Dexie('ExemploDB');

db.version(1).stores({
    obras: '++id, numeroObra, status, timestamp',
    rascunhos: '++id, numeroObra, dados, timestamp',
    uploads: '++id, tipo, dados, status',
    cache: 'key, valor, timestamp'
});

class DatabaseManager {
    static async salvarRascunho(dados) {
        const numeroObra = dados.numeroObra || 'temp_' + Date.now();
        return await db.rascunhos.add({
            numeroObra,
            dados,
            timestamp: Date.now()
        });
    }

    static async sincronizar() {
        const pendentes = await db.obras
            .where('status')
            .equals('pending')
            .toArray();

        for (const obra of pendentes) {
            try {
                await API.post('/obras', obra.dados);
                await db.obras.update(obra.id, { status: 'synced' });
            } catch (error) {
                console.error('Erro na sincronização:', error);
            }
        }
    }
}

// Auto-save a cada 30 segundos
setInterval(() => {
    const formData = coletarDadosFormulario();
    DatabaseManager.salvarRascunho(formData);
}, 30000); 