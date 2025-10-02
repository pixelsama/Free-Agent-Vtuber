#!/usr/bin/env python3
from flask import Flask, render_template, jsonify, request, Response
import subprocess
import os
import signal
import psutil
import json
import threading
import queue
from datetime import datetime
from collections import defaultdict, deque

app = Flask(__name__)

# 日志存储 - 每个服务最多保存1000条日志
service_logs = defaultdict(lambda: deque(maxlen=1000))
# 日志队列 - 用于实时推送
log_queue = queue.Queue()

SERVICE_CONFIG = {
    'dialog-engine': {
        'path': '../services/dialog-engine',
        'main': 'src/dialog_engine/app.py',
        'name': 'Dialog Engine'
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

def add_log_entry(service_id, message, log_type='info'):
    """添加日志条目"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = {
        'timestamp': timestamp,
        'service_id': service_id,
        'message': message,
        'type': log_type
    }
    service_logs[service_id].append(log_entry)
    # 添加到实时推送队列
    log_queue.put(log_entry)

def read_process_output(process, service_id):
    """读取进程输出的线程函数"""
    def read_stdout():
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                add_log_entry(service_id, output.strip(), 'stdout')
    
    def read_stderr():
        while True:
            output = process.stderr.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                add_log_entry(service_id, output.strip(), 'stderr')
    
    # 启动读取线程
    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()

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
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        running_processes[service_id] = process
        
        # 启动日志读取线程
        read_process_output(process, service_id)
        
        # 添加启动日志
        add_log_entry(service_id, f"服务启动成功: {config['name']}", 'info')
        
        return True, "服务启动成功"
    except Exception as e:
        add_log_entry(service_id, f"启动失败: {str(e)}", 'error')
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
        
        # 添加停止日志
        config = SERVICE_CONFIG.get(service_id, {})
        add_log_entry(service_id, f"服务停止成功: {config.get('name', service_id)}", 'info')
        
        return True, "服务停止成功"
    except subprocess.TimeoutExpired:
        process.kill()
        del running_processes[service_id]
        add_log_entry(service_id, f"服务强制停止成功", 'warning')
        return True, "服务强制停止成功"
    except Exception as e:
        add_log_entry(service_id, f"停止失败: {str(e)}", 'error')
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

@app.route('/api/logs')
def get_all_logs():
    """获取所有服务的日志"""
    all_logs = []
    for service_id, logs in service_logs.items():
        for log in logs:
            all_logs.append(log)
    
    # 按时间排序
    all_logs.sort(key=lambda x: x['timestamp'])
    
    # 只返回最近的500条
    return jsonify(all_logs[-500:])

@app.route('/api/logs/<service_id>')
def get_service_logs(service_id):
    """获取指定服务的日志"""
    logs = list(service_logs[service_id])
    return jsonify(logs)

@app.route('/api/logs/stream')
def log_stream():
    """实时日志流 - Server-Sent Events"""
    def event_stream():
        while True:
            try:
                # 等待新日志，超时1秒
                log_entry = log_queue.get(timeout=1)
                yield f"data: {json.dumps(log_entry)}\n\n"
            except queue.Empty:
                # 发送心跳
                yield "data: {\"type\": \"heartbeat\"}\n\n"
    
    return Response(event_stream(), mimetype='text/plain')

@app.route('/api/logs/clear/<service_id>', methods=['POST'])
def clear_service_logs(service_id):
    """清空指定服务的日志"""
    service_logs[service_id].clear()
    return jsonify({'success': True, 'message': f'已清空 {service_id} 的日志'})

@app.route('/api/logs/clear', methods=['POST'])
def clear_all_logs():
    """清空所有日志"""
    service_logs.clear()
    return jsonify({'success': True, 'message': '已清空所有日志'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)