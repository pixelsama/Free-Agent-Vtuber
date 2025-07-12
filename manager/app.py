#!/usr/bin/env python3
from flask import Flask, render_template, jsonify, request
import subprocess
import os
import signal
import psutil
import json
from datetime import datetime

app = Flask(__name__)

SERVICE_CONFIG = {
    'chat-ai-python': {
        'path': '../services/chat-ai-python',
        'main': 'main.py',
        'name': 'AI聊天模块'
    },
    'gateway-python': {
        'path': '../services/gateway-python', 
        'main': 'main.py',
        'name': '网关模块'
    },
    'input-handler-python': {
        'path': '../services/input-handler-python',
        'main': 'main.py', 
        'name': '输入处理模块'
    },
    'memory-python': {
        'path': '../services/memory-python',
        'main': 'main.py',
        'name': '记忆模块'
    },
    'output-handler-python': {
        'path': '../services/output-handler-python',
        'main': 'main.py',
        'name': '输出处理模块'
    }
}

running_processes = {}

def get_service_status(service_id):
    """获取服务状态"""
    if service_id in running_processes:
        try:
            process = running_processes[service_id]
            if process.poll() is None:
                return 'running'
            else:
                del running_processes[service_id]
                return 'stopped'
        except:
            if service_id in running_processes:
                del running_processes[service_id]
            return 'stopped'
    return 'stopped'

def start_service(service_id):
    """启动服务"""
    if service_id not in SERVICE_CONFIG:
        return False, "未知服务"
    
    if get_service_status(service_id) == 'running':
        return False, "服务已在运行"
    
    config = SERVICE_CONFIG[service_id]
    service_path = os.path.join(os.path.dirname(__file__), config['path'])
    
    if not os.path.exists(service_path):
        return False, f"服务目录不存在: {service_path}"
    
    # 检查服务目录的虚拟环境
    venv_path = os.path.join(service_path, '.venv', 'bin', 'python')
    
    if os.path.exists(venv_path):
        python_cmd = venv_path
    else:
        python_cmd = 'python3'
    
    try:
        process = subprocess.Popen(
            [python_cmd, config['main']], 
            cwd=service_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        running_processes[service_id] = process
        return True, "服务启动成功"
    except Exception as e:
        return False, f"启动失败: {str(e)}"

def stop_service(service_id):
    """停止服务"""
    if service_id not in running_processes:
        return False, "服务未运行"
    
    try:
        process = running_processes[service_id]
        process.terminate()
        process.wait(timeout=5)
        del running_processes[service_id]
        return True, "服务停止成功"
    except subprocess.TimeoutExpired:
        process.kill()
        del running_processes[service_id]
        return True, "服务强制停止成功"
    except Exception as e:
        return False, f"停止失败: {str(e)}"

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/services')
def get_services():
    """获取所有服务状态"""
    services = []
    for service_id, config in SERVICE_CONFIG.items():
        services.append({
            'id': service_id,
            'name': config['name'],
            'status': get_service_status(service_id)
        })
    return jsonify(services)

@app.route('/api/services/<service_id>/start', methods=['POST'])
def start_service_api(service_id):
    """启动指定服务"""
    success, message = start_service(service_id)
    return jsonify({'success': success, 'message': message})

@app.route('/api/services/<service_id>/stop', methods=['POST'])
def stop_service_api(service_id):
    """停止指定服务"""
    success, message = stop_service(service_id)
    return jsonify({'success': success, 'message': message})

@app.route('/api/services/<service_id>/status')
def get_service_status_api(service_id):
    """获取指定服务状态"""
    status = get_service_status(service_id)
    return jsonify({'status': status})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)