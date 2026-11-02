// Otimização do Google Maps
class MapsOptimizer {
    static defaultLocation = { lat: -15.7801, lng: -47.9292 };
    static map = null;
    static markers = new Map();

    static async initMap(element, options = {}) {
        if (!isElementInViewport(element)) return;

        const mapOptions = {
            zoom: 15,
            center: this.defaultLocation,
            gestureHandling: 'greedy',
            zoomControl: true,
            mapTypeControl: false,
            streetViewControl: false,
            fullscreenControl: false,
            ...options
        };

        if (!window.google) {
            await this.loadGoogleMapsScript();
        }

        this.map = new google.maps.Map(element, mapOptions);
        this.setupEventListeners();
    }

    static async loadGoogleMapsScript() {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = `https://maps.googleapis.com/maps/api/js?key=${YOUR_API_KEY}`;
            script.async = true;
            script.defer = true;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    static addMarker(position, title) {
        if (!this.map) return;

        const marker = new google.maps.Marker({
            position,
            map: this.map,
            title
        });

        this.markers.set(title, marker);
        return marker;
    }

    static setupEventListeners() {
        // Implementar listeners otimizados
    }
} 