# Web Dashboard Monitoring System

**Document Version**: 1.0  
**Date**: September 15, 2025  
**Status**: Planning & Architecture Phase  

This document outlines the design and implementation strategy for a comprehensive web-based monitoring dashboard for the Mobasher live TV analysis system.

---

## 📋 Overview

The Mobasher system currently uses terminal-based monitoring (`quick_status_check.sh` and "open my eyes" command). While effective, a web dashboard would provide:

- **Remote Access**: Monitor system from anywhere via web browser
- **Visual Interface**: Rich graphics, thumbnails, charts, and real-time updates
- **Historical Data**: Trend analysis and performance tracking over time
- **Professional Presentation**: Clean interface suitable for stakeholders
- **Mobile Compatibility**: Check system status on mobile devices
- **Automated Alerts**: Visual/audio notifications for issues

---

## 🎯 Architecture Options

### Option 1: Enhanced Monitor Dashboard ⭐ **RECOMMENDED**

**Description**: Extend the existing `monitor-dashboard/` directory with a full-featured web interface.

**Architecture:**
```
monitor-dashboard/
├── app.py                     # Main Flask/FastAPI application
├── config.py                  # Configuration management
├── requirements.txt           # Python dependencies
├── templates/
│   ├── base.html             # Base template with navigation
│   ├── dashboard.html        # Main dashboard page
│   ├── processes.html        # Detailed process monitoring
│   ├── archives.html         # Archive management interface  
│   ├── thumbnails.html       # Thumbnail gallery
│   └── settings.html         # Configuration interface
├── static/
│   ├── css/
│   │   ├── dashboard.css     # Main stylesheet
│   │   ├── charts.css        # Chart styling
│   │   └── responsive.css    # Mobile responsiveness
│   ├── js/
│   │   ├── dashboard.js      # Main JavaScript functionality
│   │   ├── charts.js         # Chart.js configurations
│   │   ├── realtime.js       # Server-Sent Events handling
│   │   └── thumbnails.js     # Image gallery functionality
│   └── images/
│       └── icons/            # System icons and graphics
├── api/
│   ├── __init__.py
│   ├── status.py             # System status endpoints
│   ├── processes.py          # Process monitoring APIs
│   ├── thumbnails.py         # Image serving endpoints
│   ├── metrics.py            # Performance metrics APIs
│   └── archives.py           # Archive management APIs
├── utils/
│   ├── monitoring.py         # Core monitoring functions
│   ├── database.py           # Database integration
│   └── alerts.py             # Alert management
└── tests/
    ├── test_api.py           # API endpoint tests
    └── test_monitoring.py    # Monitoring logic tests
```

**Technology Stack:**
- **Backend**: Flask 2.3+ (lightweight, easy integration)
- **Database**: PostgreSQL (reuse existing) + Redis (caching)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Charts**: Chart.js 4.0+ (excellent performance, responsive)
- **Real-time**: Server-Sent Events (SSE) or WebSocket
- **Styling**: CSS Grid/Flexbox (modern, responsive)

**Advantages:**
- ✅ Builds on existing infrastructure
- ✅ Easy to integrate with current monitoring scripts
- ✅ Full control over features and design
- ✅ Can reuse existing database connections
- ✅ Minimal additional dependencies

**Disadvantages:**
- ❌ Requires custom development
- ❌ Need to handle real-time updates manually

---

### Option 2: FastAPI Integration

**Description**: Add dashboard endpoints to the existing FastAPI application.

**Implementation Strategy:**
```python
# Add to existing mobasher/api/app.py
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")
templates = Jinja2Templates(directory="dashboard/templates")

@app.get("/dashboard")
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/api/dashboard/status")
async def dashboard_status():
    return {
        "system_health": get_system_health(),
        "processes": get_process_status(),
        "performance": get_performance_metrics()
    }
```

**Advantages:**
- ✅ Single application deployment
- ✅ Shared authentication/middleware
- ✅ Unified API structure
- ✅ Existing database connections

**Disadvantages:**
- ❌ Couples monitoring with main API
- ❌ Potential performance impact on API
- ❌ Less flexible for specialized monitoring features

---

### Option 3: Dedicated Monitoring Service

**Description**: Standalone monitoring application (micro-service architecture).

**Architecture:**
```
mobasher-monitor/
├── app/
│   ├── main.py               # FastAPI application
│   ├── models/               # Data models
│   ├── services/             # Business logic
│   ├── api/                  # REST endpoints
│   └── websocket/            # Real-time connections
├── frontend/
│   ├── src/                  # Vue.js/React source
│   ├── public/               # Static assets
│   └── dist/                 # Built files
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── deployment/
    └── nginx.conf            # Reverse proxy config
```

**Advantages:**
- ✅ Complete separation of concerns
- ✅ Scalable architecture
- ✅ Modern frontend frameworks
- ✅ Professional deployment options

**Disadvantages:**
- ❌ Complex setup and maintenance
- ❌ Additional infrastructure requirements
- ❌ Longer development time

---

## 🖥️ User Interface Design

### Main Dashboard Layout

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Mobasher System Monitor</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <header class="navbar">
        <h1>🎯 Mobasher Monitor</h1>
        <div class="status-indicator" id="connection-status">🟢 Connected</div>
        <div class="last-update">Last update: <span id="last-update">2s ago</span></div>
    </header>
    
    <main class="dashboard-grid">
        <!-- System Health Panel -->
        <section class="health-panel">
            <h2>🏥 System Health</h2>
            <div class="health-indicators">
                <div class="indicator" id="db-status">
                    <span class="status-dot">🟢</span>
                    <span>Database</span>
                    <span class="latency">2.3ms</span>
                </div>
                <!-- More indicators... -->
            </div>
        </section>
        
        <!-- Process Monitoring -->
        <section class="process-panel">
            <h2>📺 Recorders (4/6 Active)</h2>
            <div class="process-list" id="recorder-list">
                <!-- Dynamic content -->
            </div>
        </section>
        
        <section class="archive-panel">
            <h2>🗄️ Archivers (6/6 Active)</h2>
            <div class="process-list" id="archiver-list">
                <!-- Dynamic content -->
            </div>
        </section>
        
        <!-- Thumbnail Gallery -->
        <section class="thumbnail-gallery">
            <h2>📸 Live Thumbnails</h2>
            <div class="gallery-grid" id="thumbnail-grid">
                <!-- Dynamic thumbnails -->
            </div>
        </section>
        
        <!-- Performance Charts -->
        <section class="charts-panel">
            <h2>📈 Performance Metrics</h2>
            <div class="chart-container">
                <canvas id="segments-chart"></canvas>
            </div>
            <div class="chart-container">
                <canvas id="asr-pipeline-chart"></canvas>
            </div>
        </section>
        
        <!-- Resource Monitoring -->
        <section class="resources-panel">
            <h2>💻 System Resources</h2>
            <div class="resource-meters">
                <div class="meter" id="cpu-meter">
                    <span>CPU</span>
                    <div class="progress-bar">
                        <div class="progress" style="width: 45%"></div>
                    </div>
                    <span>45%</span>
                </div>
                <!-- More meters... -->
            </div>
        </section>
    </main>
</body>
</html>
```

### CSS Framework Design

```css
/* Dashboard Grid Layout */
.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
    padding: 20px;
    max-width: 1400px;
    margin: 0 auto;
}

/* Component Styling */
.health-panel, .process-panel, .archive-panel, 
.thumbnail-gallery, .charts-panel, .resources-panel {
    background: #ffffff;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    border-left: 4px solid #007bff;
}

/* Status Indicators */
.status-dot {
    display: inline-block;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    margin-right: 8px;
}

.status-dot.green { background: #28a745; }
.status-dot.yellow { background: #ffc107; }
.status-dot.red { background: #dc3545; }

/* Responsive Design */
@media (max-width: 768px) {
    .dashboard-grid {
        grid-template-columns: 1fr;
        padding: 10px;
    }
    
    .thumbnail-gallery .gallery-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}
```

---

## 📊 Dashboard Features Specification

### 1. Real-Time System Status

**Components:**
- **Health Indicators**: Database, Redis, API status with response times
- **Process Monitor**: Live process list with PIDs, uptime, resource usage
- **Alert Bar**: Prominent error/warning notifications

**Technical Implementation:**
```javascript
// Real-time updates using Server-Sent Events
const eventSource = new EventSource('/api/dashboard/events');

eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    updateSystemHealth(data.health);
    updateProcessStatus(data.processes);
    updateMetrics(data.metrics);
};

function updateSystemHealth(health) {
    document.getElementById('db-status').className = 
        `indicator ${health.db.status}`;
    document.getElementById('db-latency').textContent = 
        `${health.db.latency}ms`;
}
```

### 2. Process Monitoring Dashboard

**Recorder Monitoring:**
```html
<div class="process-card recorder" data-channel="kuwait1">
    <div class="process-header">
        <h3>Kuwait News</h3>
        <span class="status-indicator running">🟢</span>
    </div>
    <div class="process-details">
        <div class="detail-item">
            <span class="label">PID:</span>
            <span class="value">34085</span>
        </div>
        <div class="detail-item">
            <span class="label">Port:</span>
            <span class="value">9108</span>
        </div>
        <div class="detail-item">
            <span class="label">Runtime:</span>
            <span class="value" id="runtime-kuwait1">2d 15h 42m</span>
        </div>
        <div class="detail-item">
            <span class="label">CPU:</span>
            <span class="value">2.3%</span>
        </div>
        <div class="detail-item">
            <span class="label">Memory:</span>
            <span class="value">67 MB</span>
        </div>
    </div>
    <div class="process-actions">
        <button class="btn-action" onclick="viewLogs('kuwait1')">
            📝 Logs
        </button>
        <button class="btn-action" onclick="restartProcess('kuwait1')">
            🔄 Restart
        </button>
    </div>
</div>
```

### 3. Thumbnail Gallery Interface

**Gallery Implementation:**
```javascript
class ThumbnailGallery {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        this.refreshInterval = 30000; // 30 seconds
        this.init();
    }
    
    init() {
        this.loadThumbnails();
        setInterval(() => this.loadThumbnails(), this.refreshInterval);
    }
    
    async loadThumbnails() {
        try {
            const response = await fetch('/api/dashboard/thumbnails');
            const thumbnails = await response.json();
            this.renderThumbnails(thumbnails);
        } catch (error) {
            console.error('Failed to load thumbnails:', error);
        }
    }
    
    renderThumbnails(thumbnails) {
        this.container.innerHTML = thumbnails.map(thumb => `
            <div class="thumbnail-item" data-channel="${thumb.channel}">
                <img src="/api/thumbnails/${thumb.channel}/latest" 
                     alt="${thumb.channel} thumbnail"
                     onerror="this.src='/static/images/no-thumbnail.png'">
                <div class="thumbnail-info">
                    <h4>${thumb.channel_name}</h4>
                    <span class="timestamp">${thumb.timestamp}</span>
                    <span class="file-size">${thumb.size}</span>
                </div>
                <div class="thumbnail-actions">
                    <button onclick="viewFullImage('${thumb.path}')">
                        🔍 View
                    </button>
                    <button onclick="downloadImage('${thumb.path}')">
                        📥 Download
                    </button>
                </div>
            </div>
        `).join('');
    }
}
```

### 4. Performance Charts

**Chart.js Implementation:**
```javascript
class PerformanceCharts {
    constructor() {
        this.charts = {};
        this.initCharts();
    }
    
    initCharts() {
        // Segments Timeline Chart
        const segmentsCtx = document.getElementById('segments-chart').getContext('2d');
        this.charts.segments = new Chart(segmentsCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Segments Created',
                    data: [],
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Count'
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                    }
                }
            }
        });
        
        // ASR Pipeline Status Chart (Doughnut)
        const asrCtx = document.getElementById('asr-pipeline-chart').getContext('2d');
        this.charts.asr = new Chart(asrCtx, {
            type: 'doughnut',
            data: {
                labels: ['Completed', 'Pending', 'Processing', 'Failed'],
                datasets: [{
                    data: [0, 0, 0, 0],
                    backgroundColor: [
                        '#28a745',
                        '#ffc107', 
                        '#17a2b8',
                        '#dc3545'
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'right',
                    }
                }
            }
        });
    }
    
    updateSegmentsChart(timeLabels, segmentCounts) {
        const chart = this.charts.segments;
        chart.data.labels = timeLabels;
        chart.data.datasets[0].data = segmentCounts;
        chart.update('none'); // No animation for real-time updates
    }
    
    updateASRChart(completed, pending, processing, failed) {
        const chart = this.charts.asr;
        chart.data.datasets[0].data = [completed, pending, processing, failed];
        chart.update();
    }
}
```

---

## 🚀 Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Deliverables:**
- [x] Basic Flask application structure
- [x] System health monitoring endpoints
- [x] Simple dashboard HTML template
- [x] CSS framework setup
- [x] Process status display

**Technical Tasks:**
```bash
# Setup commands
cd /root/MediaView/monitor-dashboard
pip install flask jinja2 requests psutil
mkdir -p templates static/css static/js api utils
touch app.py config.py requirements.txt
```

**Core Endpoints:**
```python
@app.route('/api/status')
def system_status():
    return jsonify({
        'health': get_system_health(),
        'processes': get_process_status(),
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/thumbnails/<channel>/latest')
def latest_thumbnail(channel):
    thumbnail_path = find_latest_thumbnail(channel)
    return send_file(thumbnail_path, mimetype='image/jpeg')
```

### Phase 2: Core Features (Week 3-4)

**Deliverables:**
- [x] Real-time updates (Server-Sent Events)
- [x] Thumbnail gallery with image serving
- [x] Basic performance charts
- [x] Process management actions
- [x] Responsive mobile design

**Technical Implementation:**
```python
@app.route('/api/events')
def stream_events():
    def generate():
        while True:
            data = {
                'health': get_system_health(),
                'processes': get_process_status(),
                'metrics': get_performance_metrics()
            }
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(5)  # Update every 5 seconds
    
    return Response(generate(), mimetype='text/plain')
```

### Phase 3: Advanced Features (Week 5-6)

**Deliverables:**
- [x] Historical data storage and charts
- [x] Alert system with notifications
- [x] Configuration management interface
- [x] Export functionality (PDF/CSV reports)
- [x] Authentication and security

**Database Schema:**
```sql
CREATE TABLE dashboard_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metric_type VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    value NUMERIC NOT NULL,
    metadata JSONB
);

CREATE INDEX idx_metrics_timestamp ON dashboard_metrics(timestamp);
CREATE INDEX idx_metrics_type ON dashboard_metrics(metric_type, metric_name);
```

### Phase 4: Polish & Optimization (Week 7-8)

**Deliverables:**
- [x] Performance optimization
- [x] Error handling and logging
- [x] Comprehensive testing
- [x] Documentation and deployment guides
- [x] Dark/light theme support

---

## 📡 API Specification

### REST Endpoints

```yaml
GET /api/dashboard/status
  Description: Complete system status
  Response:
    health: {db, redis, api, storage}
    processes: {recorders[], archivers[]}
    performance: {segments, transcripts, asr_pipeline}
    resources: {cpu, memory, disk}

GET /api/dashboard/processes
  Description: Detailed process information
  Response:
    recorders: [{pid, channel, uptime, cpu, memory, status}]
    archivers: [{pid, channel, uptime, archives_today, latest_archive}]

GET /api/dashboard/thumbnails
  Description: Latest thumbnails from all channels
  Response:
    thumbnails: [{channel, path, timestamp, size, url}]

GET /api/dashboard/metrics/{timerange}
  Description: Historical performance data
  Parameters:
    timerange: 1h, 6h, 24h, 7d
  Response:
    timestamps: []
    segments: []
    transcripts: []
    resource_usage: []

POST /api/dashboard/actions/restart/{process_type}/{channel}
  Description: Restart recorder or archiver
  Authentication: Required
  Response:
    success: boolean
    message: string
    new_pid: integer

GET /api/dashboard/logs/{process_type}/{channel}
  Description: Process log streaming
  Parameters:
    lines: number (default: 100)
    follow: boolean (default: false)
  Response: Server-Sent Events stream
```

### WebSocket Events

```javascript
// Connection
const ws = new WebSocket('ws://localhost:8080/ws/dashboard');

// Incoming events
{
  "type": "status_update",
  "data": {
    "processes": {...},
    "health": {...}
  }
}

{
  "type": "alert",
  "data": {
    "level": "error|warning|info",
    "message": "Process recorder/kuwait1 has stopped",
    "timestamp": "2025-09-15T10:30:00Z"
  }
}

{
  "type": "new_thumbnail",
  "data": {
    "channel": "al_jazeera",
    "url": "/api/thumbnails/al_jazeera/latest",
    "timestamp": "2025-09-15T10:30:15Z"
  }
}
```

---

## 🔐 Security Considerations

### Authentication & Authorization
```python
from flask_login import login_required, current_user
from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/dashboard/actions/restart/<process_type>/<channel>', methods=['POST'])
@login_required
@admin_required
def restart_process(process_type, channel):
    # Implementation
    pass
```

### Security Headers
```python
@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response
```

### Input Validation
```python
from marshmallow import Schema, fields, validate

class ProcessActionSchema(Schema):
    action = fields.Str(required=True, validate=validate.OneOf(['restart', 'stop', 'start']))
    channel = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    force = fields.Bool(missing=False)
```

---

## 📱 Mobile Optimization

### Responsive Design Principles
```css
/* Mobile-first approach */
.dashboard-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 15px;
    padding: 10px;
}

/* Tablet */
@media (min-width: 768px) {
    .dashboard-grid {
        grid-template-columns: repeat(2, 1fr);
        gap: 20px;
        padding: 20px;
    }
}

/* Desktop */
@media (min-width: 1024px) {
    .dashboard-grid {
        grid-template-columns: repeat(3, 1fr);
        max-width: 1400px;
        margin: 0 auto;
    }
}

/* Touch-friendly interactions */
.btn-action {
    min-height: 44px;
    min-width: 44px;
    padding: 12px 16px;
    font-size: 16px;
}
```

### Progressive Web App (PWA) Features
```javascript
// Service Worker for offline functionality
self.addEventListener('fetch', event => {
    if (event.request.url.includes('/api/dashboard/status')) {
        event.respondWith(
            caches.match(event.request)
                .then(response => response || fetch(event.request))
        );
    }
});

// Web App Manifest
{
    "name": "Mobasher Monitor",
    "short_name": "Mobasher",
    "start_url": "/dashboard",
    "display": "standalone",
    "theme_color": "#007bff",
    "background_color": "#ffffff",
    "icons": [
        {
            "src": "/static/icons/icon-192.png",
            "sizes": "192x192",
            "type": "image/png"
        }
    ]
}
```

---

## 🎨 Theming & Customization

### CSS Custom Properties
```css
:root {
    --primary-color: #007bff;
    --success-color: #28a745;
    --warning-color: #ffc107;
    --danger-color: #dc3545;
    --info-color: #17a2b8;
    
    --bg-primary: #ffffff;
    --bg-secondary: #f8f9fa;
    --text-primary: #333333;
    --text-secondary: #666666;
    
    --border-radius: 8px;
    --box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    --transition: all 0.3s ease;
}

[data-theme="dark"] {
    --bg-primary: #2d3748;
    --bg-secondary: #1a202c;
    --text-primary: #ffffff;
    --text-secondary: #a0aec0;
    --box-shadow: 0 2px 4px rgba(0,0,0,0.3);
}
```

### Theme Switcher
```javascript
class ThemeManager {
    constructor() {
        this.currentTheme = localStorage.getItem('theme') || 'light';
        this.applyTheme(this.currentTheme);
        this.setupToggle();
    }
    
    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    }
    
    toggleTheme() {
        const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        this.currentTheme = newTheme;
        this.applyTheme(newTheme);
    }
    
    setupToggle() {
        const toggle = document.getElementById('theme-toggle');
        toggle.addEventListener('click', () => this.toggleTheme());
    }
}
```

---

## 🚀 Deployment & Infrastructure

### Production Deployment
```yaml
# docker-compose.yml
version: '3.8'
services:
  dashboard:
    build: ./monitor-dashboard
    ports:
      - "8080:8080"
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=postgresql://user:pass@db:5432/mobasher
      - REDIS_URL=redis://redis:6379/1
    volumes:
      - /mnt/volume_ams3_03/mediaview-data/data:/app/data:ro
    depends_on:
      - redis
    restart: unless-stopped
  
  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
    restart: unless-stopped

volumes:
  redis-data:
```

### Nginx Configuration
```nginx
server {
    listen 80;
    server_name monitor.yourdomain.com;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /api/events {
        proxy_pass http://localhost:8080;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
        proxy_buffering off;
        proxy_cache off;
    }
    
    location /static {
        alias /path/to/dashboard/static;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }
}
```

### Environment Configuration
```python
# config.py
import os
from pathlib import Path

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    DATABASE_URL = os.environ.get('DATABASE_URL') or 'postgresql://mobasher:mobasher@localhost/mobasher'
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/1'
    
    MOBASHER_DATA_ROOT = Path(os.environ.get('MOBASHER_DATA_ROOT', '/mnt/volume_ams3_03/mediaview-data/data'))
    THUMBNAIL_CACHE_TTL = int(os.environ.get('THUMBNAIL_CACHE_TTL', 300))
    UPDATE_INTERVAL = int(os.environ.get('UPDATE_INTERVAL', 5))
    
    # Security
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    
class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    DEBUG = False
    
    # Logging
    LOG_LEVEL = 'INFO'
    LOG_FILE = '/var/log/mobasher-dashboard.log'
```

---

## 📊 Performance Considerations

### Caching Strategy
```python
from flask_caching import Cache
import redis

# Redis caching
cache = Cache(config={'CACHE_TYPE': 'RedisCache', 'CACHE_REDIS_URL': 'redis://localhost:6379/1'})

@cache.memoize(timeout=30)
def get_system_health():
    """Cache system health for 30 seconds"""
    return fetch_system_health()

@cache.memoize(timeout=60)
def get_thumbnail_metadata():
    """Cache thumbnail metadata for 1 minute"""
    return scan_thumbnail_directory()
```

### Database Optimization
```python
# Use connection pooling
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)

# Optimize queries
def get_recent_metrics(hours=24):
    """Efficient metrics query with proper indexing"""
    return session.query(DashboardMetric)\
        .filter(DashboardMetric.timestamp >= datetime.utcnow() - timedelta(hours=hours))\
        .order_by(DashboardMetric.timestamp.desc())\
        .limit(1000)\
        .all()
```

### Frontend Optimization
```javascript
// Debounced updates
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Optimized chart updates
const debouncedChartUpdate = debounce((chartData) => {
    performanceCharts.updateCharts(chartData);
}, 1000);

// Lazy loading for images
const imageObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const img = entry.target;
            img.src = img.dataset.src;
            img.classList.remove('lazy');
            observer.unobserve(img);
        }
    });
});
```

---

## 🧪 Testing Strategy

### Unit Tests
```python
# test_api.py
import unittest
from unittest.mock import patch, MagicMock
from dashboard.app import app

class TestDashboardAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('dashboard.api.status.get_system_health')
    def test_system_status_endpoint(self, mock_health):
        mock_health.return_value = {
            'db': {'status': 'ok', 'latency': 2.3},
            'redis': {'status': 'ok', 'latency': 1.1}
        }
        
        response = self.app.get('/api/status')
        self.assertEqual(response.status_code, 200)
        
        data = response.get_json()
        self.assertIn('health', data)
        self.assertEqual(data['health']['db']['status'], 'ok')

    def test_thumbnail_endpoint(self):
        response = self.app.get('/api/thumbnails/kuwait1/latest')
        # Should return 200 or 404, not 500
        self.assertIn(response.status_code, [200, 404])
```

### Integration Tests
```python
# test_integration.py
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
import time

class TestDashboardIntegration:
    def setup_class(self):
        self.driver = webdriver.Chrome()
        self.driver.implicitly_wait(10)
    
    def test_dashboard_loads(self):
        self.driver.get("http://localhost:8080/dashboard")
        assert "Mobasher Monitor" in self.driver.title
    
    def test_real_time_updates(self):
        self.driver.get("http://localhost:8080/dashboard")
        
        # Wait for initial load
        time.sleep(2)
        
        # Check if status indicators are present
        health_panel = self.driver.find_element(By.CLASS_NAME, "health-panel")
        assert health_panel.is_displayed()
        
        # Wait for real-time update
        time.sleep(6)
        
        # Verify content updated
        last_update = self.driver.find_element(By.ID, "last-update")
        assert "ago" in last_update.text
    
    def teardown_class(self):
        self.driver.quit()
```

### Performance Tests
```python
# test_performance.py
import time
import asyncio
from locust import HttpUser, task, between

class DashboardUser(HttpUser):
    wait_time = between(1, 5)
    
    @task(3)
    def view_dashboard(self):
        self.client.get("/dashboard")
    
    @task(2)
    def check_status(self):
        self.client.get("/api/status")
    
    @task(1)
    def view_thumbnails(self):
        self.client.get("/api/thumbnails")
    
    def on_start(self):
        # Simulate user authentication if required
        pass
```

---

## 📚 Documentation & Maintenance

### API Documentation
```yaml
# openapi.yml
openapi: 3.0.0
info:
  title: Mobasher Dashboard API
  version: 1.0.0
  description: Real-time monitoring dashboard for Mobasher system

paths:
  /api/dashboard/status:
    get:
      summary: Get complete system status
      responses:
        '200':
          description: System status retrieved successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  health:
                    type: object
                    properties:
                      db:
                        type: object
                        properties:
                          status:
                            type: string
                            enum: [ok, error]
                          latency:
                            type: number
                            description: Response time in milliseconds
```

### User Guide
```markdown
# Mobasher Dashboard User Guide

## Getting Started
1. Navigate to http://your-server:8080/dashboard
2. The dashboard automatically refreshes every 5 seconds
3. All status indicators use color coding:
   - 🟢 Green: Normal operation
   - 🟡 Yellow: Warning/degraded performance
   - 🔴 Red: Error/service down

## Main Dashboard Sections

### System Health Panel
Shows the status of core services:
- Database connection and response time
- Redis cache availability
- API service status
- Storage usage and availability

### Process Monitoring
Real-time status of all recorders and archivers:
- Process ID and uptime
- Resource usage (CPU, memory)
- Channel-specific information
- Action buttons for management

### Thumbnail Gallery
Latest screenshots from each channel:
- Automatic refresh every 30 seconds
- Click to view full-size image
- Download options available
- Shows capture timestamp and file size
```

### Maintenance Procedures
```bash
#!/bin/bash
# maintenance.sh - Dashboard maintenance procedures

# 1. Log rotation
find /var/log/mobasher-dashboard* -name "*.log" -mtime +7 -delete

# 2. Cache cleanup
redis-cli -n 1 FLUSHDB

# 3. Thumbnail cleanup (keep last 100 per channel)
for channel in kuwait_news al_jazeera al_arabiya sky_news_arabia al_ekhbariya cnbc_arabia; do
    find "/mnt/volume_ams3_03/mediaview-data/data/archive/$channel" -name "*-thumb.jpg" \
        | sort -r | tail -n +101 | xargs rm -f
done

# 4. Database maintenance
psql -d mobasher -c "DELETE FROM dashboard_metrics WHERE timestamp < NOW() - INTERVAL '30 days';"
psql -d mobasher -c "VACUUM ANALYZE dashboard_metrics;"

# 5. Health check
curl -f http://localhost:8080/api/status || echo "Dashboard health check failed"
```

---

## 🔮 Future Enhancements

### Advanced Analytics
- **Machine Learning Integration**: Predict system failures based on historical patterns
- **Anomaly Detection**: Automatically flag unusual behavior in metrics
- **Capacity Planning**: Resource usage projections and scaling recommendations

### Enhanced User Experience
- **Custom Dashboards**: User-configurable layouts and widgets
- **Advanced Filtering**: Complex queries for logs and metrics
- **Export Features**: PDF reports, CSV data export, scheduled reports

### Integration Capabilities
- **Slack/Discord Integration**: Alert notifications to team channels
- **Email Reporting**: Automated daily/weekly system reports
- **External Monitoring**: Integration with Prometheus, Grafana, New Relic

### Mobile App
- **Native Mobile App**: React Native or Flutter application
- **Push Notifications**: Critical alerts on mobile devices
- **Offline Mode**: Cached data for viewing when connection is poor

---

## 📝 Implementation Checklist

### Phase 1 Requirements
- [ ] Flask application structure
- [ ] Basic HTML templates with responsive design
- [ ] System status API endpoints
- [ ] Process monitoring functionality
- [ ] CSS framework and styling
- [ ] Basic error handling and logging

### Phase 2 Requirements
- [ ] Real-time updates (SSE implementation)
- [ ] Thumbnail serving and gallery
- [ ] Chart.js integration for metrics
- [ ] Process management actions
- [ ] Mobile optimization
- [ ] Caching layer implementation

### Phase 3 Requirements
- [ ] Historical data storage
- [ ] Advanced chart visualizations
- [ ] Alert system with notifications
- [ ] User authentication and authorization
- [ ] Configuration management interface
- [ ] Performance optimization

### Phase 4 Requirements
- [ ] Comprehensive testing suite
- [ ] Documentation and deployment guides
- [ ] Security hardening
- [ ] Production deployment configuration
- [ ] Monitoring and maintenance procedures

---

This document serves as the complete technical specification for implementing a web-based monitoring dashboard for the Mobasher system. It provides detailed guidance for developers, system administrators, and stakeholders involved in the project.

**Next Steps:**
1. Review and approve the architectural approach
2. Set up development environment
3. Begin Phase 1 implementation
4. Establish testing and deployment procedures
