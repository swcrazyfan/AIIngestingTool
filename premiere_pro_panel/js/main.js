/**
 * AI Video Ingest Tool - Main Panel Logic
 * Integrates with Python backend via HTTP API
 */

// Immediate debug log to verify JavaScript is loading
console.log('🔥 MAIN.JS LOADING - This should appear immediately!');
alert('JavaScript is working! Check console for details.');

class VideoIngestPanel {
    constructor() {
        this.csInterface = new CSInterface();
        this.apiBaseUrl = 'http://localhost:8000/api';
        this.selectedDirectory = null;
        this.ingestResults = [];
        this.searchResults = [];
        this.progressInterval = null;
        this.connectionCheckInterval = null;
        this.isAuthenticated = false;
        this.currentUser = null;
        
        console.log('🎬 VideoIngestPanel constructor called');
        console.log('🌐 API Base URL:', this.apiBaseUrl);
        
        // Bind methods
        this.init = this.init.bind(this);
        this.checkConnection = this.checkConnection.bind(this);
        this.checkAuthStatus = this.checkAuthStatus.bind(this);
        this.login = this.login.bind(this);
        this.logout = this.logout.bind(this);
        this.selectDirectory = this.selectDirectory.bind(this);
        this.startIngest = this.startIngest.bind(this);
        this.searchVideos = this.searchVideos.bind(this);
        
        this.init();
    }

    init() {
        console.log('🚀 Initializing AI Video Ingest Panel...');
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Start connection monitoring
        this.startConnectionMonitoring();
        
        // Check authentication status
        this.checkAuthStatus();
        
        // Load existing videos
        this.loadExistingVideos();
        
        console.log('✅ Panel initialized successfully');
    }

    setupEventListeners() {
        // Authentication
        document.getElementById('loginBtn').addEventListener('click', this.login);
        document.getElementById('logoutBtn').addEventListener('click', this.logout);
        document.getElementById('passwordInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.login();
        });

        // Directory selection
        document.getElementById('selectDirectory').addEventListener('click', this.selectDirectory);
        
        // Processing
        document.getElementById('startIngest').addEventListener('click', this.startIngest);
        
        // Search
        document.getElementById('searchBtn').addEventListener('click', this.searchVideos);
        document.getElementById('searchInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.searchVideos();
        });
        
        document.getElementById('clearSearch').addEventListener('click', () => {
            document.getElementById('searchInput').value = '';
            this.loadExistingVideos();
        });
        
        // Refresh
        document.getElementById('refreshResults').addEventListener('click', () => {
            this.loadExistingVideos();
        });
        
        // Options dependency - embeddings requires database
        document.getElementById('generateEmbeddings').addEventListener('change', (e) => {
            if (e.target.checked) {
                document.getElementById('storeDatabase').checked = true;
            }
        });
    }

    startConnectionMonitoring() {
        this.checkConnection();
        this.connectionCheckInterval = setInterval(this.checkConnection, 10000); // Every 10 seconds
    }

    async checkAuthStatus() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/auth/status`, {
                method: 'GET'
            });

            if (response.ok) {
                const data = await response.json();
                this.updateAuthStatus(data.authenticated, data.user);
            } else {
                this.updateAuthStatus(false);
            }
        } catch (error) {
            console.warn('Auth status check failed:', error);
            this.updateAuthStatus(false);
        }
    }

    updateAuthStatus(isAuthenticated, user = null) {
        this.isAuthenticated = isAuthenticated;
        this.currentUser = user;

        const loginForm = document.getElementById('loginForm');
        const userInfo = document.getElementById('userInfo');
        const authStatus = document.getElementById('authStatus');

        if (isAuthenticated && user) {
            loginForm.style.display = 'none';
            userInfo.style.display = 'block';
            document.getElementById('userEmail').textContent = user.email || 'Unknown';
            authStatus.textContent = '✅ Authenticated';
            authStatus.className = 'progress-text success';
        } else {
            loginForm.style.display = 'block';
            userInfo.style.display = 'none';
            authStatus.textContent = '🔐 Please log in to access database features';
            authStatus.className = 'progress-text warning';
        }

        // Update UI based on auth status
        this.updateUIForAuthStatus();
    }

    updateUIForAuthStatus() {
        const storeDatabase = document.getElementById('storeDatabase');
        const generateEmbeddings = document.getElementById('generateEmbeddings');
        
        if (!this.isAuthenticated) {
            // Disable database features if not authenticated
            storeDatabase.checked = false;
            generateEmbeddings.checked = false;
            storeDatabase.disabled = true;
            generateEmbeddings.disabled = true;
        } else {
            storeDatabase.disabled = false;
            generateEmbeddings.disabled = false;
        }
    }

    async login() {
        const email = document.getElementById('emailInput').value.trim();
        const password = document.getElementById('passwordInput').value;
        const authStatus = document.getElementById('authStatus');

        if (!email || !password) {
            authStatus.textContent = '❌ Please enter email and password';
            authStatus.className = 'progress-text error';
            return;
        }

        try {
            authStatus.textContent = '🔄 Logging in...';
            authStatus.className = 'progress-text';

            const response = await fetch(`${this.apiBaseUrl}/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            if (response.ok && data.success) {
                this.updateAuthStatus(true, data.user);
                // Clear form
                document.getElementById('emailInput').value = '';
                document.getElementById('passwordInput').value = '';
            } else {
                authStatus.textContent = `❌ ${data.error || 'Login failed'}`;
                authStatus.className = 'progress-text error';
            }
        } catch (error) {
            console.error('Login error:', error);
            authStatus.textContent = '❌ Connection error';
            authStatus.className = 'progress-text error';
        }
    }

    async logout() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/auth/logout`, {
                method: 'POST'
            });

            // Update UI regardless of response (local logout)
            this.updateAuthStatus(false);
        } catch (error) {
            console.error('Logout error:', error);
            // Still update UI for local logout
            this.updateAuthStatus(false);
        }
    }

    async checkConnection() {
        try {
            console.log('🔍 Checking API connection to:', `${this.apiBaseUrl}/health`);
            
            const response = await fetch(`${this.apiBaseUrl}/health`, {
                method: 'GET',
                timeout: 5000
            });
            
            console.log('📡 API Response status:', response.status);
            
            if (response.ok) {
                const data = await response.json();
                console.log('✅ API Response data:', data);
                this.updateConnectionStatus(true);
            } else {
                console.error('❌ API Response not OK:', response.status, response.statusText);
                this.updateConnectionStatus(false);
            }
        } catch (error) {
            console.error('❌ API connection check failed:', error);
            console.error('Error details:', {
                name: error.name,
                message: error.message,
                stack: error.stack
            });
            this.updateConnectionStatus(false);
        }
    }

    updateConnectionStatus(isConnected) {
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.status-text');
        
        if (isConnected) {
            statusDot.className = 'status-dot online';
            statusText.textContent = 'Connected';
        } else {
            statusDot.className = 'status-dot offline';
            statusText.textContent = 'API Offline';
        }
    }    async selectDirectory() {
        try {
            console.log('📂 Opening directory selection dialog...');
            
            // Use CEP file dialog to select directory
            const result = await this.csInterface.evalScript(`
                var folder = Folder.selectDialog("Select video directory to process");
                if (folder) {
                    folder.fsName;
                } else {
                    null;
                }
            `);
            
            console.log('Directory selection result:', result);
            
            if (result && result !== 'null' && result !== 'undefined') {
                this.selectedDirectory = result.replace(/"/g, ''); // Remove quotes
                document.getElementById('selectedPath').textContent = this.selectedDirectory;
                document.getElementById('selectedPath').style.display = 'block';
                document.getElementById('startIngest').disabled = false;
                
                console.log('✅ Directory selected:', this.selectedDirectory);
            } else {
                console.log('❌ No directory selected');
            }
        } catch (error) {
            console.error('Error selecting directory:', error);
            this.showError('Failed to open directory dialog');
        }
    }

    async startIngest() {
        if (!this.selectedDirectory) {
            this.showError('Please select a directory first');
            return;
        }

        console.log('🚀 Starting ingest process...');

        const options = {
            directory: this.selectedDirectory,
            recursive: document.getElementById('recursive').checked,
            ai_analysis: document.getElementById('aiAnalysis').checked,
            generate_embeddings: document.getElementById('generateEmbeddings').checked,
            store_database: document.getElementById('storeDatabase').checked
        };

        console.log('Ingest options:', options);

        try {
            this.showProgress(true);
            this.updateProgress(0, 'Starting ingest process...');
            
            // Start the ingest job
            const response = await fetch(`${this.apiBaseUrl}/ingest`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(options)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log('Ingest job started:', result);

            // Start monitoring progress
            this.startProgressMonitoring();

        } catch (error) {
            console.error('Failed to start ingest:', error);
            this.showError('Failed to start processing: ' + error.message);
            this.showProgress(false);
        }
    }

    startProgressMonitoring() {
        this.progressInterval = setInterval(async () => {
            try {
                const response = await fetch(`${this.apiBaseUrl}/ingest/progress`);
                if (response.ok) {
                    const progress = await response.json();
                    this.handleProgressUpdate(progress);
                }
            } catch (error) {
                console.error('Progress check failed:', error);
            }
        }, 1000); // Check every second
    }    handleProgressUpdate(progress) {
        console.log('Progress update:', progress);
        
        this.updateProgress(progress.progress || 0, progress.message || 'Processing...');
        
        // Update stats if available
        if (progress.results_count !== undefined) {
            document.getElementById('processedCount').textContent = progress.results_count;
            document.getElementById('progressStats').style.display = 'block';
        }
        
        if (progress.failed_count !== undefined) {
            document.getElementById('failedCount').textContent = progress.failed_count;
        }
        
        // Check if completed
        if (progress.status === 'completed' || progress.status === 'error') {
            this.stopProgressMonitoring();
            
            if (progress.status === 'completed') {
                console.log('✅ Ingest completed successfully');
                this.updateProgress(100, 'Processing completed!');
                setTimeout(() => {
                    this.showProgress(false);
                    this.loadIngestResults();
                }, 2000);
            } else {
                console.error('❌ Ingest failed:', progress.message);
                this.showError('Processing failed: ' + progress.message);
                this.showProgress(false);
            }
        }
    }

    stopProgressMonitoring() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
    }

    async loadIngestResults() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/ingest/results`);
            if (response.ok) {
                const data = await response.json();
                this.ingestResults = data.results || [];
                this.displayResults(this.ingestResults);
                console.log(`📊 Loaded ${this.ingestResults.length} processed videos`);
            }
        } catch (error) {
            console.error('Failed to load ingest results:', error);
        }
    }

    async searchVideos() {
        const query = document.getElementById('searchInput').value.trim();
        const searchType = document.getElementById('searchType').value;
        
        console.log(`🔍 Searching for: "${query}" (${searchType})`);
        
        if (!query) {
            this.loadExistingVideos();
            return;
        }

        // Check if authentication is required for database search
        if (['semantic', 'hybrid', 'transcripts'].includes(searchType) && !this.isAuthenticated) {
            this.showError('Database search requires authentication. Please log in first.');
            return;
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/search`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: query,
                    search_type: searchType,
                    limit: 20
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.searchResults = data.results || [];
                this.displayResults(this.searchResults);
                console.log(`📊 Found ${this.searchResults.length} matching videos`);
            } else if (response.status === 401) {
                this.showError('Authentication required for search. Please log in.');
            } else {
                throw new Error(`Search failed: ${response.status}`);
            }
            }
        } catch (error) {
            console.error('Search failed:', error);
            this.showError('Search failed: ' + error.message);
        }
    }    async loadExistingVideos() {
        try {
            console.log('📚 Loading existing videos...');
            const response = await fetch(`${this.apiBaseUrl}/search`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: '',
                    search_type: 'recent',
                    limit: 50
                })
            });

            if (response.ok) {
                const data = await response.json();
                const results = data.results || [];
                this.displayResults(results);
                console.log(`📊 Loaded ${results.length} existing videos`);
            }
        } catch (error) {
            console.log('No existing videos found or API unavailable');
            this.displayResults([]);
        }
    }

    displayResults(results) {
        const videoList = document.getElementById('videoList');
        const emptyState = document.getElementById('emptyState');
        const resultsCount = document.getElementById('resultsCount');
        
        // Update count
        resultsCount.textContent = `${results.length} video${results.length !== 1 ? 's' : ''}`;
        
        if (results.length === 0) {
            emptyState.style.display = 'block';
            videoList.innerHTML = emptyState.outerHTML;
            return;
        }
        
        emptyState.style.display = 'none';
        
        // Build HTML for all videos
        const videosHTML = results.map(video => this.createVideoItemHTML(video)).join('');
        videoList.innerHTML = videosHTML;
        
        // Add event listeners to action buttons
        this.attachVideoActionListeners();
    }

    createVideoItemHTML(video) {
        const duration = this.formatDuration(video.duration_seconds || 0);
        const camera = [video.camera_make, video.camera_model].filter(Boolean).join(' ') || 'Unknown';
        const summary = video.content_summary || 'No summary available';
        const tags = (video.content_tags || []).slice(0, 5); // Show max 5 tags
        
        return `
            <div class="video-item" data-video-id="${video.id}">
                <div class="video-info">
                    <div class="video-title">${this.escapeHtml(video.file_name)}</div>
                    <div class="video-meta">${duration} • ${this.escapeHtml(camera)}</div>
                    <div class="video-summary">${this.escapeHtml(summary)}</div>
                    <div class="video-tags">
                        ${tags.map(tag => `<span class="tag">${this.escapeHtml(tag)}</span>`).join('')}
                    </div>
                </div>
                <div class="video-actions">
                    <button class="btn secondary" onclick="panel.addToTimeline('${this.escapeHtml(video.local_path || video.file_path)}')">
                        ➕ Timeline
                    </button>
                    <button class="btn secondary" onclick="panel.addToProject('${this.escapeHtml(video.local_path || video.file_path)}')">
                        📁 Import
                    </button>
                    <button class="btn secondary" onclick="panel.revealInFinder('${this.escapeHtml(video.local_path || video.file_path)}')">
                        👁️ Reveal
                    </button>
                </div>
            </div>
        `;
    }    attachVideoActionListeners() {
        // Event listeners are handled via onclick attributes in HTML
        // This approach works better with CEP's security model
    }

    async addToTimeline(filePath) {
        try {
            console.log('📽️ Adding to timeline:', filePath);
            
            const result = await this.csInterface.evalScript(`
                try {
                    var project = app.project;
                    var sequence = project.activeSequence;
                    
                    if (!sequence) {
                        "No active sequence. Please create or select a sequence first.";
                    } else {
                        // Import the file first
                        var imported = project.importFiles(["${filePath.replace(/\\/g, '\\\\')}"]);
                        
                        if (imported && imported.length > 0) {
                            var projectItem = imported[0];
                            
                            // Get current playhead position
                            var currentTime = sequence.getPlayerPosition();
                            
                            // Add to timeline at current position
                            var success = sequence.insertClip(projectItem, currentTime, 0, 0);
                            
                            if (success) {
                                "Video added to timeline successfully!";
                            } else {
                                "Failed to add video to timeline.";
                            }
                        } else {
                            "Failed to import video file.";
                        }
                    }
                } catch (e) {
                    "Error: " + e.toString();
                }
            `);
            
            console.log('Timeline result:', result);
            
            if (result.includes('successfully')) {
                this.showSuccess('Video added to timeline!');
            } else {
                this.showError(result);
            }
            
        } catch (error) {
            console.error('Failed to add to timeline:', error);
            this.showError('Failed to add video to timeline');
        }
    }

    async addToProject(filePath) {
        try {
            console.log('📁 Importing to project:', filePath);
            
            const result = await this.csInterface.evalScript(`
                try {
                    var project = app.project;
                    var imported = project.importFiles(["${filePath.replace(/\\/g, '\\\\')}"]);
                    
                    if (imported && imported.length > 0) {
                        "Video imported to project panel successfully!";
                    } else {
                        "Failed to import video file.";
                    }
                } catch (e) {
                    "Error: " + e.toString();
                }
            `);
            
            console.log('Import result:', result);
            
            if (result.includes('successfully')) {
                this.showSuccess('Video imported to project!');
            } else {
                this.showError(result);
            }
            
        } catch (error) {
            console.error('Failed to import to project:', error);
            this.showError('Failed to import video to project');
        }
    }    async revealInFinder(filePath) {
        try {
            console.log('👁️ Revealing in Finder:', filePath);
            
            const result = await this.csInterface.evalScript(`
                try {
                    var file = new File("${filePath.replace(/\\/g, '\\\\')}");
                    if (file.exists) {
                        file.execute();
                        "File revealed in Finder successfully!";
                    } else {
                        "File not found at: ${filePath}";
                    }
                } catch (e) {
                    "Error: " + e.toString();
                }
            `);
            
            console.log('Reveal result:', result);
            
            if (result.includes('successfully')) {
                this.showSuccess('File revealed in Finder!');
            } else {
                this.showError(result);
            }
            
        } catch (error) {
            console.error('Failed to reveal in finder:', error);
            this.showError('Failed to reveal file in Finder');
        }
    }

    // UI Helper Methods
    showProgress(show, message = 'Processing...') {
        const section = document.getElementById('progressSection');
        if (show) {
            section.style.display = 'block';
            this.updateProgress(0, message);
        } else {
            section.style.display = 'none';
        }
    }

    updateProgress(percent, message) {
        document.getElementById('progressFill').style.width = `${percent}%`;
        document.getElementById('progressPercent').textContent = `${Math.round(percent)}%`;
        document.getElementById('progressText').textContent = message;
    }

    showError(message) {
        console.error('Error:', message);
        // You could implement a toast notification system here
        alert('Error: ' + message);
    }

    showSuccess(message) {
        console.log('Success:', message);
        // You could implement a toast notification system here
        // For now, we'll just log it
    }

    formatDuration(seconds) {
        if (!seconds || seconds <= 0) return '0:00';
        
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Cleanup
    destroy() {
        if (this.connectionCheckInterval) {
            clearInterval(this.connectionCheckInterval);
        }
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }
    }
}

// Initialize the panel when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎬 Starting AI Video Ingest Panel...');
    window.panel = new VideoIngestPanel();
});

// Cleanup on unload
window.addEventListener('beforeunload', function() {
    if (window.panel) {
        window.panel.destroy();
    }
});