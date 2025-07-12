class ServiceManager {
    constructor() {
        this.services = [];
        this.init();
    }

    init() {
        this.loadServices();
        this.bindEvents();
        this.startAutoRefresh();
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