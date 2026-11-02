// Compressão e manipulação de imagens
class ImageHandler {
  static async compressImage(file) {
    const options = {
      maxSizeMB: 1,
      maxWidthOrHeight: 1920,
      useWebWorker: true,
      quality: 0.8
    };
    return await imageCompression(file, options);
  }

  static createPreview(file, previewElement) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = document.createElement('img');
      img.src = e.target.result;
      img.className = 'img-preview';
      previewElement.innerHTML = '';
      previewElement.appendChild(img);
    };
    reader.readAsDataURL(file);
  }

  static async uploadInBackground(files) {
    const uploads = [];
    for (const file of files) {
      const compressed = await this.compressImage(file);
      uploads.push(db.uploads.add({
        file: compressed,
        status: 'pending',
        timestamp: Date.now()
      }));
    }
    return Promise.all(uploads);
  }
} 