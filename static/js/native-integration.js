// Integração com recursos nativos
class NativeIntegration {
  static async initQRScanner() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      // Implementar scanner de QR code
    } catch (error) {
      console.error('Erro ao acessar câmera:', error);
    }
  }
} 