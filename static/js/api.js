// API otimizada com cache
class API {
  static baseURL = 'https://api.example.com';
  static cacheTime = 5 * 60 * 1000; // 5 minutos

  static async request(endpoint, options = {}) {
    const url = this.baseURL + endpoint;
    const cacheKey = `api_${url}_${JSON.stringify(options)}`;

    // Verificar cache
    const cached = await db.cache.get(cacheKey);
    if (cached && !this.isCacheExpired(cached.timestamp)) {
      return cached.data;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      // Atualizar cache
      await db.cache.put({
        key: cacheKey,
        data,
        timestamp: Date.now()
      });

      return data;
    } catch (error) {
      console.error('API error:', error);
      throw error;
    }
  }

  static isCacheExpired(timestamp) {
    return Date.now() - timestamp > this.cacheTime;
  }

  static async get(endpoint) {
    return this.request(endpoint);
  }

  static async post(endpoint, data) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }
} 