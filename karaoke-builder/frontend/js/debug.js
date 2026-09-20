/**
 * Karaoke Builder — Debug Console
 * 
 * Handles debug log display and management
 */

class DebugConsole {
    constructor() {
        this.container = document.getElementById('logs-container');
        this.autoScroll = true;
    }
    
    /**
     * Add log entry to console
     */
    addLog(entry) {
        const div = document.createElement('div');
        div.className = 'log-entry';
        
        const timestamp = this.formatTimestamp(entry.timestamp);
        const level = entry.level.toLowerCase();
        const message = entry.message;
        
        div.innerHTML = `
            <span class="log-timestamp">${timestamp}</span>
            <span class="log-level log-${level}">${level.toUpperCase()}</span>
            <span class="log-message">${this.escapeHtml(message)}</span>
        `;
        
        this.container.appendChild(div);
        
        if (this.autoScroll) {
            this.container.scrollTop = this.container.scrollHeight;
        }
    }
    
    /**
     * Add multiple log entries
     */
    addLogs(entries) {
        entries.forEach(entry => this.addLog(entry));
    }
    
    /**
     * Clear all logs
     */
    clear() {
        this.container.innerHTML = '';
    }
    
    /**
     * Refresh logs from server
     */
    async refresh() {
        try {
            const logs = await window.api.getLogs();
            this.clear();
            this.addLogs(logs);
        } catch (error) {
            this.addLog({
                timestamp: new Date().toISOString(),
                level: 'ERROR',
                message: `Failed to load logs: ${error.message}`
            });
        }
    }
    
    /**
     * Copy logs to clipboard
     */
    async copyToClipboard() {
        try {
            const report = await window.api.getDebugReport();
            await navigator.clipboard.writeText(report);
            alert('Debug report copied to clipboard!');
        } catch (error) {
            alert(`Failed to copy: ${error.message}`);
        }
    }
    
    /**
     * Save logs to file
     */
    async saveToFile() {
        try {
            const result = await window.api.saveLog();
            alert(`Log saved to: ${result.filepath}`);
        } catch (error) {
            alert(`Failed to save log: ${error.message}`);
        }
    }
    
    /**
     * Format ISO timestamp to readable time
     */
    formatTimestamp(isoString) {
        if (!isoString) return '--:--:--';
        
        const date = new Date(isoString);
        return date.toLocaleTimeString('ru-RU', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }
    
    /**
     * Escape HTML special characters
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export singleton instance
window.debugConsole = new DebugConsole();
