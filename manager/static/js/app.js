class ServiceManager {
    constructor() {
        this.services = [];
        this.eventSource = null;
        this.init();
    }

    init() {
        this.loadServices();
        this.bindEvents();
        this.startAutoRefresh();
        this.initLogModal();
    }

    async loadServices() {
        try {
            const response = await fetch('/api/services');
            this.services = await response.json();
            this.renderServices();
        } catch (error) {
            this.addLog('加载服务列表失败: ' + error.message, 'error');
        }
    }

    renderServices() {
        const grid = document.getElementById('servicesGrid');
        grid.innerHTML = '';

        this.services.forEach(service => {
            const card = this.createServiceCard(service);
            grid.appendChild(card);
        });
    }

    createServiceCard(service) {
        const card = document.createElement('div');
        card.className = `service-card ${service.status}`;
        card.innerHTML = `
            <div class="service-header">
                <div class="service-name">${service.name}</div>
                <div class="status-badge ${service.status}">
                    ${service.status === 'running' ? '运行中' : '已停止'}
                </div>
            </div>
            <div class="service-actions">
                <button class="btn btn-success start-btn" 
                        data-service="${service.id}" 
                        ${service.status === 'running' ? 'disabled' : ''}>
                    ▶️ 启动
                </button>
                <button class="btn btn-danger stop-btn" 
                        data-service="${service.id}"
                        ${service.status === 'stopped' ? 'disabled' : ''}>
                    ⏹️ 停止
                </button>
            </div>
        `;

        // 绑定事件
        const startBtn = card.querySelector('.start-btn');
        const stopBtn = card.querySelector('.stop-btn');

        startBtn.addEventListener('click', () => this.startService(service.id));
        stopBtn.addEventListener('click', () => this.stopService(service.id));

        return card;
    }

    async startService(serviceId) {
        this.addLog(`正在启动服务: ${this.getServiceName(serviceId)}`);
        
        try {
            const response = await fetch(`/api/services/${serviceId}/start`, {
                method: 'POST'
            });
            const result = await response.json();
            
            if (result.success) {
                this.addLog(`服务启动成功: ${this.getServiceName(serviceId)}`, 'success');
            } else {
                this.addLog(`服务启动失败: ${result.message}`, 'error');
            }
            
            this.loadServices(); // 刷新状态
        } catch (error) {
            this.addLog(`启动服务失败: ${error.message}`, 'error');
        }
    }

    async stopService(serviceId) {
        this.addLog(`正在停止服务: ${this.getServiceName(serviceId)}`);
        
        try {
            const response = await fetch(`/api/services/${serviceId}/stop`, {
                method: 'POST'
            });
            const result = await response.json();
            
            if (result.success) {
                this.addLog(`服务停止成功: ${this.getServiceName(serviceId)}`, 'success');
            } else {
                this.addLog(`服务停止失败: ${result.message}`, 'error');
            }
            
            this.loadServices(); // 刷新状态
        } catch (error) {
            this.addLog(`停止服务失败: ${error.message}`, 'error');
        }
    }

    async startAllServices() {
        this.addLog('正在启动所有服务...');
        const stoppedServices = this.services.filter(s => s.status === 'stopped');
        
        for (const service of stoppedServices) {
            await this.startService(service.id);
            await this.sleep(1000); // 间隔1秒启动
        }
    }

    async stopAllServices() {
        this.addLog('正在停止所有服务...');
        const runningServices = this.services.filter(s => s.status === 'running');
        
        for (const service of runningServices) {
            await this.stopService(service.id);
            await this.sleep(500); // 间隔0.5秒停止
        }
    }

    getServiceName(serviceId) {
        const service = this.services.find(s => s.id === serviceId);
        return service ? service.name : serviceId;
    }

    addLog(message, type = 'info') {
        const logContainer = document.getElementById('logContainer');
        const logItem = document.createElement('p');
        logItem.className = `log-item ${type}`;
        
        const timestamp = new Date().toLocaleTimeString();
        logItem.textContent = `[${timestamp}] ${message}`;
        
        logContainer.appendChild(logItem);
        logContainer.scrollTop = logContainer.scrollHeight;

        // 保持最多50条日志
        const logs = logContainer.children;
        if (logs.length > 50) {
            logContainer.removeChild(logs[0]);
        }
    }

    bindEvents() {
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.addLog('刷新服务状态...');
            this.loadServices();
        });

        document.getElementById('startAllBtn').addEventListener('click', () => {
            this.startAllServices();
        });

        document.getElementById('stopAllBtn').addEventListener('click', () => {
            this.stopAllServices();
        });

        document.getElementById('showLogsBtn').addEventListener('click', () => {
            this.showLogModal();
        });
    }

    initLogModal() {
        const modal = document.getElementById('logModal');
        const closeBtn = modal.querySelector('.close');
        
        // 关闭模态框
        closeBtn.addEventListener('click', () => {
            this.hideLogModal();
        });
        
        // 点击背景关闭
        window.addEventListener('click', (event) => {
            if (event.target === modal) {
                this.hideLogModal();
            }
        });

        // 绑定日志控制事件
        document.getElementById('serviceSelector').addEventListener('change', (e) => {
            this.loadServiceLogs(e.target.value);
        });

        document.getElementById('refreshLogsBtn').addEventListener('click', () => {
            const selectedService = document.getElementById('serviceSelector').value;
            this.loadServiceLogs(selectedService);
        });

        document.getElementById('clearLogsBtn').addEventListener('click', () => {
            this.clearLogs();
        });

        document.getElementById('realTimeCheck').addEventListener('change', (e) => {
            if (e.target.checked) {
                this.startRealTimeLogs();
            } else {
                this.stopRealTimeLogs();
            }
        });
    }

    showLogModal() {
        const modal = document.getElementById('logModal');
        modal.style.display = 'block';
        
        // 更新服务选择器
        this.updateServiceSelector();
        
        // 默认加载所有日志
        this.loadServiceLogs('all');
    }

    hideLogModal() {
        const modal = document.getElementById('logModal');
        modal.style.display = 'none';
        
        // 停止实时日志
        this.stopRealTimeLogs();
        document.getElementById('realTimeCheck').checked = false;
    }

    updateServiceSelector() {
        const selector = document.getElementById('serviceSelector');
        selector.innerHTML = '<option value="all">所有服务</option>';
        
        this.services.forEach(service => {
            const option = document.createElement('option');
            option.value = service.id;
            option.textContent = service.name;
            selector.appendChild(option);
        });
    }

    async loadServiceLogs(serviceId) {
        try {
            const url = serviceId === 'all' ? '/api/logs' : `/api/logs/${serviceId}`;
            const response = await fetch(url);
            const logs = await response.json();
            
            this.displayLogs(logs);
        } catch (error) {
            console.error('加载日志失败:', error);
        }
    }

    displayLogs(logs) {
        const container = document.getElementById('serviceLogContainer');
        container.innerHTML = '';
        
        if (logs.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: #888; margin-top: 50px;">暂无日志</div>';
            return;
        }
        
        logs.forEach(log => {
            const logEntry = this.createLogEntry(log);
            container.appendChild(logEntry);
        });
        
        // 自动滚动到底部
        if (document.getElementById('autoScrollCheck').checked) {
            container.scrollTop = container.scrollHeight;
        }
    }

    createLogEntry(log) {
        const entry = document.createElement('div');
        entry.className = `log-entry ${log.type}`;
        
        const timestamp = document.createElement('span');
        timestamp.className = 'log-timestamp';
        timestamp.textContent = log.timestamp;
        
        const service = document.createElement('span');
        service.className = 'log-service';
        service.textContent = `[${this.getServiceName(log.service_id)}]`;
        
        const message = document.createElement('span');
        message.className = 'log-message';
        message.textContent = log.message;
        
        entry.appendChild(timestamp);
        entry.appendChild(service);
        entry.appendChild(message);
        
        return entry;
    }

    async clearLogs() {
        const selectedService = document.getElementById('serviceSelector').value;
        
        try {
            const url = selectedService === 'all' ? '/api/logs/clear' : `/api/logs/clear/${selectedService}`;
            const response = await fetch(url, { method: 'POST' });
            const result = await response.json();
            
            if (result.success) {
                this.loadServiceLogs(selectedService);
                this.addLog(`已清空日志: ${selectedService === 'all' ? '所有服务' : this.getServiceName(selectedService)}`, 'success');
            }
        } catch (error) {
            this.addLog(`清空日志失败: ${error.message}`, 'error');
        }
    }

    startRealTimeLogs() {
        if (this.eventSource) {
            this.eventSource.close();
        }
        
        this.eventSource = new EventSource('/api/logs/stream');
        
        this.eventSource.onmessage = (event) => {
            const log = JSON.parse(event.data);
            
            if (log.type === 'heartbeat') {
                return;
            }
            
            // 检查是否需要显示这条日志
            const selectedService = document.getElementById('serviceSelector').value;
            if (selectedService !== 'all' && selectedService !== log.service_id) {
                return;
            }
            
            // 添加到日志容器
            const container = document.getElementById('serviceLogContainer');
            const logEntry = this.createLogEntry(log);
            container.appendChild(logEntry);
            
            // 限制显示的日志数量
            const entries = container.children;
            if (entries.length > 500) {
                container.removeChild(entries[0]);
            }
            
            // 自动滚动
            if (document.getElementById('autoScrollCheck').checked) {
                container.scrollTop = container.scrollHeight;
            }
        };
        
        this.eventSource.onerror = (error) => {
            console.error('实时日志连接错误:', error);
            this.stopRealTimeLogs();
        };
    }

    stopRealTimeLogs() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

    startAutoRefresh() {
        // 每10秒自动刷新状态
        setInterval(() => {
            this.loadServices();
        }, 10000);
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    new ServiceManager();
});