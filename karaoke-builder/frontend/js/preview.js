/**
 * Karaoke Builder — Preview Player
 * 
 * Handles audio playback with synchronized lyrics display
 */

class KaraokePreview {
    constructor() {
        this.audio = document.getElementById('audio-player');
        this.progressBar = document.getElementById('progress-bar');
        this.currentTimeEl = document.getElementById('current-time');
        this.totalDurationEl = document.getElementById('total-duration');
        this.btnPlay = document.getElementById('btn-play');
        this.btnStop = document.getElementById('btn-stop');
        
        this.currentLineEl = document.getElementById('current-line');
        this.previousLineEl = document.getElementById('previous-line');
        this.nextLineEl = document.getElementById('next-line');
        
        this.timelineContainer = document.getElementById('timeline-container');
        this.debugContent = document.getElementById('debug-content');
        
        this.karaokeData = null;
        this.isPlaying = false;
        this.updateInterval = null;
        
        this.init();
    }
    
    async init() {
        try {
            // Load karaoke JSON from backend
            const response = await fetch('/api/output/karaoke.json');
            
            if (!response.ok) {
                throw new Error('Karaoke JSON not found. Run pipeline first.');
            }
            
            this.karaokeData = await response.json();
            
            // Load audio
            this.audio.src = '/api/output/minus.mp3';
            
            // Setup event listeners
            this.setupEventListeners();
            
            // Initialize UI
            this.initializeUI();
            
            this.log('Preview initialized successfully');
            
        } catch (error) {
            this.showError(`Failed to load preview: ${error.message}`);
        }
    }
    
    setupEventListeners() {
        // Play/Pause button
        this.btnPlay.addEventListener('click', () => this.togglePlay());
        
        // Stop button
        this.btnStop.addEventListener('click', () => this.stop());
        
        // Progress bar
        this.progressBar.addEventListener('input', () => this.seek());
        
        // Audio events
        this.audio.addEventListener('timeupdate', () => this.onTimeUpdate());
        this.audio.addEventListener('loadedmetadata', () => this.onLoadedMetadata());
        this.audio.addEventListener('ended', () => this.onEnded());
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space') {
                e.preventDefault();
                this.togglePlay();
            } else if (e.code === 'ArrowLeft') {
                this.audio.currentTime = Math.max(0, this.audio.currentTime - 5);
            } else if (e.code === 'ArrowRight') {
                this.audio.currentTime = Math.min(this.audio.duration, this.audio.currentTime + 5);
            }
        });
    }
    
    initializeUI() {
        // Display song info
        const metadata = this.karaokeData.metadata || {};
        
        // Render timeline
        this.renderTimeline();
        
        // Show debug info
        this.renderDebugInfo();
        
        // Set initial lyrics
        this.updateLyricsDisplay(0);
    }
    
    renderTimeline() {
        const lines = this.karaokeData.lyrics?.lines || [];
        const duration = this.karaokeData.metadata?.duration || 180;
        
        this.timelineContainer.innerHTML = '';
        
        lines.forEach((line, index) => {
            const marker = document.createElement('div');
            marker.className = 'timeline-marker';
            
            const leftPercent = (line.start / duration) * 100;
            const width = Math.max(2, ((line.end - line.start) / duration) * 100);
            
            marker.style.left = `${leftPercent}%`;
            marker.style.width = `${width}%`;
            
            marker.innerHTML = `
                <span class="timeline-label">${this.escapeHtml(line.text.substring(0, 20))}</span>
            `;
            
            marker.addEventListener('click', () => {
                this.audio.currentTime = line.start;
                if (!this.isPlaying) {
                    this.togglePlay();
                }
            });
            
            this.timelineContainer.appendChild(marker);
        });
    }
    
    renderDebugInfo() {
        const metadata = this.karaokeData.metadata || {};
        const lyrics = this.karaokeData.lyrics || {};
        const pitch = this.karaokeData.pitch || {};
        
        let html = `
            <h3>Metadata</h3>
            <table>
                <tr><td>Title</td><td>${this.escapeHtml(metadata.title || 'N/A')}</td></tr>
                <tr><td>Duration</td><td>${this.formatTime(metadata.duration || 0)}</td></tr>
                <tr><td>Format Version</td><td>${this.karaokeData.version || '1'}</td></tr>
            </table>
            
            <h3>Lyrics</h3>
            <table>
                <tr><td>Total Lines</td><td>${lyrics.lines?.length || 0}</td></tr>
                <tr><td>Total Words</td><td>${this.countWords()}</td></tr>
            </table>
            
            <h3>Pitch</h3>
            <table>
                <tr><td>Data Points</td><td>${pitch.points?.length || 0}</td></tr>
                <tr><td>Sample Rate</td><td>${pitch.metadata?.sample_rate || 'N/A'} Hz</td></tr>
            </table>
        `;
        
        this.debugContent.innerHTML = html;
    }
    
    countWords() {
        const lines = this.karaokeData.lyrics?.lines || [];
        return lines.reduce((total, line) => {
            return total + (line.words?.length || 0);
        }, 0);
    }
    
    togglePlay() {
        if (this.isPlaying) {
            this.pause();
        } else {
            this.play();
        }
    }
    
    play() {
        this.audio.play().then(() => {
            this.isPlaying = true;
            this.btnPlay.textContent = '⏸ Pause';
            this.startUpdateLoop();
        }).catch(error => {
            this.log(`Playback error: ${error.message}`);
        });
    }
    
    pause() {
        this.audio.pause();
        this.isPlaying = false;
        this.btnPlay.textContent = '▶ Play';
        this.stopUpdateLoop();
    }
    
    stop() {
        this.pause();
        this.audio.currentTime = 0;
        this.updateLyricsDisplay(0);
    }
    
    seek() {
        const value = parseFloat(this.progressBar.value);
        const duration = this.audio.duration;
        this.audio.currentTime = (value / 100) * duration;
    }
    
    onTimeUpdate() {
        const currentTime = this.audio.currentTime;
        const duration = this.audio.duration;
        
        // Update progress bar
        if (duration > 0) {
            const percent = (currentTime / duration) * 100;
            this.progressBar.value = percent;
        }
        
        // Update time display
        this.currentTimeEl.textContent = this.formatTime(currentTime);
        
        // Update lyrics
        this.updateLyricsDisplay(currentTime);
    }
    
    onLoadedMetadata() {
        this.totalDurationEl.textContent = this.formatTime(this.audio.duration);
    }
    
    onEnded() {
        this.isPlaying = false;
        this.btnPlay.textContent = '▶ Play';
        this.stopUpdateLoop();
    }
    
    startUpdateLoop() {
        this.stopUpdateLoop();
        this.updateInterval = setInterval(() => {
            // Force update check
            this.onTimeUpdate();
        }, 100);
    }
    
    stopUpdateLoop() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
    
    updateLyricsDisplay(currentTime) {
        const lines = this.karaokeData.lyrics?.lines || [];
        
        // Find current line
        let currentIndex = -1;
        let previousIndex = -1;
        let nextIndex = -1;
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            
            if (line.start <= currentTime && line.end >= currentTime) {
                currentIndex = i;
                break;
            }
            
            if (line.end < currentTime) {
                previousIndex = i;
            }
            
            if (line.start > currentTime && nextIndex === -1) {
                nextIndex = i;
            }
        }
        
        // Update display
        this.currentLineEl.textContent = currentIndex >= 0 
            ? lines[currentIndex].text 
            : '...';
        
        this.previousLineEl.textContent = previousIndex >= 0 
            ? lines[previousIndex].text 
            : '';
        
        this.nextLineEl.textContent = nextIndex >= 0 
            ? lines[nextIndex].text 
            : '';
        
        // Highlight current line in timeline
        this.highlightTimeline(currentIndex);
    }
    
    highlightTimeline(currentIndex) {
        const markers = this.timelineContainer.querySelectorAll('.timeline-marker');
        markers.forEach((marker, index) => {
            if (index === currentIndex) {
                marker.style.background = 'rgba(233, 69, 96, 0.3)';
            } else {
                marker.style.background = 'transparent';
            }
        });
    }
    
    formatTime(seconds) {
        if (isNaN(seconds) || seconds < 0) return '00:00';
        
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    log(message) {
        console.log('[Preview]', message);
    }
    
    showError(message) {
        this.debugContent.innerHTML = `<p style="color:#f87171;">${message}</p>`;
    }
}

// Initialize preview when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.preview = new KaraokePreview();
});
