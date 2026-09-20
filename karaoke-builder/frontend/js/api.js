/**
 * Karaoke Builder — API Client
 * 
 * Handles communication with backend REST API
 */

const API_BASE = '';

class ApiClient {
    /**
     * Make API request
     */
    async request(endpoint, options = {}) {
        const url = `${API_BASE}${endpoint}`;
        
        const config = {
            headers: {
                'Content-Type': 'application/json',
            },
            ...options
        };
        
        try {
            const response = await fetch(url, config);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || `HTTP ${response.status}`);
            }
            
            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }
    
    /**
     * GET request
     */
    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }
    
    /**
     * POST request
     */
    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    // System endpoints
    async getSystemInfo() {
        return this.get('/api/system/info');
    }
    
    async getSystemReadiness() {
        return this.get('/api/system/readiness');
    }
    
    // Validation
    async validateProject(mp3Path, txtPath, title) {
        return this.post('/api/validate', {
            mp3_path: mp3Path,
            txt_path: txtPath,
            title: title
        });
    }
    
    // Pipeline
    async startPipeline(mp3Path, txtPath, title) {
        return this.post('/api/pipeline/start', {
            mp3_path: mp3Path,
            txt_path: txtPath,
            title: title
        });
    }
    
    async runStage(stageName) {
        return this.post(`/api/pipeline/stage/${stageName}`);
    }
    
    // Logs
    async getLogs(stage = null) {
        const endpoint = stage 
            ? `/api/logs?stage=${stage}`
            : '/api/logs';
        return this.get(endpoint);
    }
    
    async getDebugReport() {
        const response = await fetch(`${API_BASE}/api/logs/report`);
        return response.text();
    }
    
    async saveLog() {
        return this.post('/api/logs/save');
    }
}

// Export singleton instance
window.api = new ApiClient();
