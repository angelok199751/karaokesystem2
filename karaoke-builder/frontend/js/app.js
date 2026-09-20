/**
 * Karaoke Builder — Main Application Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    // Initialize application
    const app = new KaraokeBuilderApp();
    app.init();
});

class KaraokeBuilderApp {
    constructor() {
        this.mp3File = null;
        this.txtFile = null;
        this.currentJobId = null;
        this.failedStage = null;
        
        // DOM elements
        this.elements = {
            systemStatus: document.getElementById('system-status'),
            statusContent: document.getElementById('status-content'),
            btnCheckSystem: document.getElementById('btn-check-system'),
            
            projectForm: document.getElementById('project-form'),
            mp3DropZone: document.getElementById('mp3-drop-zone'),
            txtDropZone: document.getElementById('txt-drop-zone'),
            mp3Input: document.getElementById('mp3-input'),
            txtInput: document.getElementById('txt-input'),
            mp3Info: document.getElementById('mp3-info'),
            txtInfo: document.getElementById('txt-info'),
            titleInput: document.getElementById('title'),
            btnCreate: document.getElementById('btn-create'),
            
            pipelineProgress: document.getElementById('pipeline-progress'),
            pipelineError: document.getElementById('pipeline-error'),
            pipelineActions: document.getElementById('pipeline-actions'),
            btnOpenPreview: document.getElementById('btn-open-preview'),
            btnRetry: document.getElementById('btn-retry'),
            
            debugConsole: window.debugConsole
        };
    }
    
    async init() {
        // Setup event listeners
        this.setupEventListeners();
        
        // Check system on load
        await this.checkSystem();
        
        // Initial log
        this.elements.debugConsole.addLog({
            timestamp: new Date().toISOString(),
            level: 'INFO',
            message: 'Application initialized'
        });
    }
    
    setupEventListeners() {
        // System check button
        this.elements.btnCheckSystem.addEventListener('click', () => this.checkSystem());
        
        // Form submission
        this.elements.projectForm.addEventListener('submit', (e) => this.handleSubmit(e));
        
        // File inputs
        this.elements.mp3Input.addEventListener('change', (e) => this.handleFileSelect(e, 'mp3'));
        this.elements.txtInput.addEventListener('change', (e) => this.handleFileSelect(e, 'txt'));
        
        // Drag and drop
        this.setupDragDrop(this.elements.mp3DropZone, 'mp3');
        this.setupDragDrop(this.elements.txtDropZone, 'txt');
        
        // Debug console buttons
        document.getElementById('btn-refresh-logs').addEventListener('click', () => {
            this.elements.debugConsole.refresh();
        });
        
        document.getElementById('btn-copy-logs').addEventListener('click', () => {
            this.elements.debugConsole.copyToClipboard();
        });
        
        document.getElementById('btn-save-logs').addEventListener('click', () => {
            this.elements.debugConsole.saveToFile();
        });
        
        document.getElementById('btn-clear-logs').addEventListener('click', () => {
            this.elements.debugConsole.clear();
        });
        
        // Pipeline actions
        this.elements.btnOpenPreview.addEventListener('click', () => this.openPreview());
        this.elements.btnRetry.addEventListener('click', () => this.retryFailedStage());
    }
    
    setupDragDrop(dropZone, type) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.add('dragover');
            }, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.remove('dragover');
            }, false);
        });
        
        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            if (files.length > 0) {
                const file = files[0];
                this.handleFile(file, type);
            }
        }, false);
    }
    
    handleFileSelect(e, type) {
        const file = e.target.files[0];
        if (file) {
            this.handleFile(file, type);
        }
    }
    
    handleFile(file, type) {
        if (type === 'mp3') {
            this.mp3File = file;
            this.elements.mp3Info.innerHTML = `
                <strong>${file.name}</strong><br>
                Size: ${this.formatSize(file.size)}
            `;
        } else if (type === 'txt') {
            this.txtFile = file;
            this.elements.txtInfo.innerHTML = `
                <strong>${file.name}</strong><br>
                Size: ${this.formatSize(file.size)}
            `;
        }
        
        this.updateCreateButton();
    }
    
    updateCreateButton() {
        const canCreate = this.mp3File && this.txtFile;
        this.elements.btnCreate.disabled = !canCreate;
    }
    
    async checkSystem() {
        try {
            this.elements.statusContent.innerHTML = '<p>Loading...</p>';
            
            const readiness = await window.api.getSystemReadiness();
            
            let html = '<table style="width:100%;text-align:left;">';
            html += '<tr><th>Component</th><th>Status</th></tr>';
            
            for (const [name, info] of Object.entries(readiness.components)) {
                const icon = info.available ? '✓' : '✗';
                const color = info.available ? '#4ade80' : (info.required ? '#f87171' : '#fbbf24');
                html += `
                    <tr>
                        <td>${name.charAt(0).toUpperCase() + name.slice(1)}</td>
                        <td style="color:${color}">${icon} ${info.available ? 'OK' : 'Missing'}</td>
                    </tr>
                `;
            }
            
            html += '</table>';
            
            if (!readiness.ready) {
                html += `<p style="color:#f87171;margin-top:10px;">
                    ⚠ Missing required components: ${readiness.missing_required.join(', ')}
                </p>`;
            } else {
                html += `<p style="color:#4ade80;margin-top:10px;">✓ System ready</p>`;
            }
            
            this.elements.statusContent.innerHTML = html;
            
        } catch (error) {
            this.elements.statusContent.innerHTML = `
                <p style="color:#f87171;">Error: ${error.message}</p>
            `;
        }
    }
    
    async handleSubmit(e) {
        e.preventDefault();
        
        if (!this.mp3File || !this.txtFile) {
            alert('Please select both MP3 and TXT files');
            return;
        }
        
        const title = this.elements.titleInput.value.trim() || this.mp3File.name.replace(/\.[^/.]+$/, "");
        
        // Show pipeline progress
        this.elements.pipelineProgress.style.display = 'block';
        this.elements.pipelineError.style.display = 'none';
        this.elements.pipelineActions.style.display = 'none';
        
        // Reset stages
        document.querySelectorAll('.stage').forEach(stage => {
            stage.className = 'stage';
            stage.querySelector('.stage-status').textContent = 'Waiting...';
        });
        
        try {
            // Start pipeline
            this.setStageStatus('validation', 'processing', 'Validating...');
            
            const result = await window.api.startPipeline(
                this.mp3File.path || `/tmp/${this.mp3File.name}`,
                this.txtFile.path || `/tmp/${this.txtFile.name}`,
                title
            );
            
            if (result.success) {
                this.onPipelineSuccess(result);
            } else {
                this.onPipelineFailure(result);
            }
            
        } catch (error) {
            this.onPipelineFailure({
                success: false,
                error: error.message
            });
        }
    }
    
    setStageStatus(stageName, status, message) {
        const stage = document.querySelector(`[data-stage="${stageName}"]`);
        if (!stage) return;
        
        stage.className = `stage ${status}`;
        stage.querySelector('.stage-status').textContent = message;
        
        const icons = {
            waiting: '⏳',
            processing: '⚙️',
            success: '✓',
            error: '✗'
        };
        stage.querySelector('.stage-icon').textContent = icons[status] || '⏳';
    }
    
    onPipelineSuccess(result) {
        // Mark all stages as success
        ['validation', 'demucs', 'whisperx', 'pitch', 'packaging'].forEach(stage => {
            this.setStageStatus(stage, 'success', 'Completed');
        });
        
        this.currentJobId = result.job_id;
        
        // Show preview button
        this.elements.btnOpenPreview.style.display = 'inline-block';
        this.elements.pipelineActions.style.display = 'block';
        
        this.elements.debugConsole.addLog({
            timestamp: new Date().toISOString(),
            level: 'INFO',
            message: 'Pipeline completed successfully!'
        });
    }
    
    onPipelineFailure(result) {
        // Find failed stage
        const results = result.results || {};
        let failedStage = null;
        
        for (const [stage, data] of Object.entries(results)) {
            if (!data.success) {
                failedStage = stage;
                this.setStageStatus(stage, 'error', `Failed: ${data.error_message || 'Error'}`);
            } else {
                this.setStageStatus(stage, 'success', 'Completed');
            }
        }
        
        this.failedStage = failedStage;
        
        // Show error
        const errorMessage = result.error || 'Pipeline failed';
        this.elements.pipelineError.textContent = errorMessage;
        this.elements.pipelineError.style.display = 'block';
        
        // Show retry button if we have a failed stage
        if (failedStage) {
            this.elements.btnRetry.style.display = 'inline-block';
        }
        
        this.elements.pipelineActions.style.display = 'block';
        
        this.elements.debugConsole.addLog({
            timestamp: new Date().toISOString(),
            level: 'ERROR',
            message: `Pipeline failed at ${failedStage}: ${errorMessage}`
        });
    }
    
    async retryFailedStage() {
        if (!this.failedStage) return;
        
        try {
            this.setStageStatus(this.failedStage, 'processing', 'Retrying...');
            
            const result = await window.api.runStage(this.failedStage);
            
            if (result.success) {
                this.setStageStatus(this.failedStage, 'success', 'Completed');
                this.elements.btnRetry.style.display = 'none';
                
                // If this was the last stage, show preview button
                if (this.failedStage === 'packaging') {
                    this.elements.btnOpenPreview.style.display = 'inline-block';
                }
            } else {
                this.setStageStatus(this.failedStage, 'error', 'Failed again');
            }
            
        } catch (error) {
            this.setStageStatus(this.failedStage, 'error', `Error: ${error.message}`);
        }
    }
    
    openPreview() {
        // Open preview in new window
        window.open('preview.html', '_blank');
    }
    
    formatSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
}
