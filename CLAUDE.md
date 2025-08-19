# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is a Free-Agent-Vtuber project built with a **microservices event-driven architecture** using Redis as the central message bus. All services communicate through Redis queues (lists) and channels (pub/sub), making the system highly decoupled and scalable.

### Core Architecture Pattern
- **Event-Driven**: Services communicate through Redis message bus
- **Polyglot**: Supports multiple programming languages (currently Python + Vue.js)
- **Decoupled**: Services are independent and can be developed/deployed separately
- **Scalable**: New functionality can be added as separate microservices

### Message Flow (Critical Understanding)
1. **Input Flow**: External → Gateway → ASR → input-handler → user_input_queue
2. **Processing**: memory consumes user_input_queue → memory_updates → chat-ai → ai_responses + tts_requests
3. **Output Flow**: tts consumes tts_requests → task_response channels → output/gateway

The system uses "B模式：content优先" where services prioritize reading `task_data.content` over `input_file`.

## Development Commands

### Frontend (Vue.js + Vite + Live2D)
```bash
cd front_end
npm install              # Install dependencies
npm run dev             # Start development server (http://localhost:5173)
npm run build           # Build for production
npm run preview         # Preview production build
```

### Backend Services (Python microservices)
Each service in `services/` directory has independent environment:

```bash
# For any service (e.g., chat-ai-python, memory-python, etc.)
cd services/[service-name]
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py           # Start the service
```

### Testing
```bash
# Root level - install dev dependencies for testing
pip install -r requirements-dev.txt

# Service level testing
cd services/[service-name]
pytest                   # Run all tests
pytest tests/unit/       # Unit tests only
pytest tests/integration/ # Integration tests (requires Redis)
pytest --cov=. --cov-report=html  # With coverage
```

### Docker Deployment
```bash
# Production deployment
docker compose up -d
docker compose ps        # Check status
docker compose logs -f   # View logs

# Development with hot reload (automatically detects code changes)
docker compose -f docker-compose.dev.yml up -d

# Stop services
docker compose down
```

### Docker Container Updates
When making code changes, use these commands to update containers:

```bash
# RECOMMENDED: Standard rebuild and restart
docker compose up -d --build [service-name]

# Restart without rebuild (for config-only changes)
docker compose restart [service-name]

# Full rebuild all services
docker compose up -d --build

# For troubleshooting: Force no-cache rebuild (rare cases)
docker compose build --no-cache [service-name]
docker compose up -d [service-name]

# Check if changes are applied
docker compose logs --tail=10 [service-name]
```

**Notes:**
- Always use `docker compose` (V2) instead of `docker-compose` (V1)
- Docker's cache is reliable - `--build` detects code changes correctly
- Only use `--no-cache` for troubleshooting rare caching issues
- Monitor logs to verify services are running correctly

### Local Management (Alternative to Docker)
```bash
cd manager
pip install -r requirements.txt
python app.py           # Starts Flask manager at http://localhost:5000
```

### Code Quality Tools
```bash
# Available in requirements-dev.txt
black .                 # Code formatting
isort .                 # Import sorting  
flake8 .               # Code linting
mypy .                 # Type checking
```

## Key Service Contracts

### Redis Message Channels/Queues
- `asr_tasks` (list): Audio recognition tasks
- `asr_results` (pub/sub): ASR recognition results
- `user_input_queue` (list): Standardized user input tasks
- `memory_updates` (pub/sub): Memory storage notifications
- `ai_responses` (pub/sub): AI chat responses
- `tts_requests` (list): Text-to-speech synthesis tasks
- `task_response:{task_id}` (pub/sub): Individual task responses

### Standard Task Format (user_input_queue)
```json
{
  "task_id": "inherited_from_upstream",
  "type": "text|audio",
  "user_id": "anonymous",
  "content": "recognized_text_preferred",
  "input_file": "/path/to/file_fallback",
  "source": "asr|user|system",
  "timestamp": 1234567890,
  "meta": {
    "trace_id": "...",
    "lang": "zh",
    "from_channel": "asr_results",
    "provider": "fake|openai_whisper|funasr_local"
  }
}
```

## Service Architecture

### Core Services
- **gateway-python**: HTTP/WebSocket API gateway (port 8000)
- **asr-python**: Automatic Speech Recognition (supports fake/OpenAI/FunASR)
- **input-handler-python**: Bridges ASR results to standardized input queue
- **memory-python**: User conversation memory management
- **chat-ai-python**: AI conversation processing (OpenAI-compatible APIs)
- **tts-python**: Text-to-speech synthesis (Edge-TTS, OpenAI TTS)
- **output-handler-python**: Response output handling

### Frontend & Management
- **front_end/**: Vue.js + Vuetify + Live2D virtual character interface
- **manager/**: Flask-based local development service manager

### Configuration
- Each service has `config.json` for service-specific settings
- Environment variables override config values (e.g., `OPENAI_API_KEY`)
- Redis connection configurable via `REDIS_HOST`/`REDIS_PORT`

## Development Guidelines

### Service Startup Order (Important)
1. Redis
2. gateway  
3. asr
4. input-handler (should log "ASR bridge subscribed to channel: asr_results")
5. memory
6. chat-ai
7. tts
8. output

### Testing Service Integration
```bash
# Test end-to-end flow
curl -X POST http://localhost:8000/api/asr -F "audio_file=@test.wav"
# Should trigger: asr_results → input-handler → memory → chat-ai → tts → output
```

### Adding New Services
1. Create new directory in `services/`
2. Add `Dockerfile`, `requirements.txt`, `config.json`, `main.py`
3. Update `docker-compose.yml` if using Docker deployment
4. Follow Redis pub/sub or queue patterns for communication
5. Add corresponding tests in `tests/` directory

### Configuration Priority
1. Environment variables (highest)
2. `config.json` files
3. Default values (lowest)

## Hot Reload Development Environment

### Overview
The project supports **automatic hot reload** for pure Python microservices during development. When you modify code, the affected service automatically restarts without requiring container rebuilds.

### Hot Reload Architecture
- **Framework Services** (with native hot reload):
  - `gateway-python`: FastAPI (uvicorn reload=True) + Flask (FLASK_DEBUG=1)
  - `input-handler-python`: FastAPI (uvicorn reload=True) 
  - `output-handler-python`: FastAPI (uvicorn reload=True)

- **Pure Python Services** (custom hot reload):
  - `asr-python`: Uses watchdog-based hot reload
  - `chat-ai-python`: Uses watchdog-based hot reload
  - `memory-python`: Uses watchdog-based hot reload  
  - `tts-python`: Uses watchdog-based hot reload

### Hot Reload Features
- **File Monitoring**: Watches `.py` and `.json` files for changes
- **Smart Restart**: 1-second debounce to avoid excessive restarts
- **Process Management**: Graceful service restart with proper cleanup
- **Real-time Logs**: Shows restart events and service status
- **Container Compatible**: Works seamlessly in Docker development environment

### Usage
```bash
# Start development environment with hot reload
docker compose -f docker-compose.dev.yml up -d

# View hot reload logs for a specific service
docker compose -f docker-compose.dev.yml logs [service-name] -f

# Example log output when file changes:
# 2025-08-19 03:13:32,165 - hot_reload - INFO - 文件变更检测到，正在重启服务...
# 2025-08-19 03:13:32,200 - hot_reload - INFO - 启动进程: /usr/local/bin/python main.py
```

### Implementation Details
- **Framework Hot Reload**: 
  - FastAPI: `uvicorn.run(..., reload=True)` for automatic Python file monitoring
  - Flask: `FLASK_ENV=development` + `FLASK_DEBUG=1` for debug mode with auto-restart
- **Custom Hot Reload Module**: `utils/hot_reload.py` - Watchdog-based file monitoring for pure Python services
- **Service Runners**: `services/*/dev_runner.py` - Development-specific entry points for non-framework services
- **Dependencies**: Pure Python services include `watchdog>=3.0.0` in requirements.txt
- **Docker Integration**: Development compose uses appropriate entry points based on service type

### Monitored File Types
- `.py` files: Python source code changes
- `.json` files: Configuration file changes
- Excluded: `__pycache__`, `.pyc`, `.git`, `venv/`, test files

### Troubleshooting Hot Reload
```bash
# Check if hot reload is active
docker compose -f docker-compose.dev.yml logs [service-name] --tail=10

# Look for these log messages:
# "启动热重载管理器" - Hot reload manager started
# "开始监控目录" - Directory monitoring started
# "文件变更检测到" - File change detected
```

## Important Files
- `docker-compose.yml`: Production container orchestration
- `docker-compose.dev.yml`: Development environment with hot reload
- `utils/hot_reload.py`: Shared hot reload implementation
- `services/*/dev_runner.py`: Development entry points for pure Python services
- `requirements-dev.txt`: Shared development and testing dependencies  
- `front_end/vite.config.js`: Frontend build configuration
- `services/*/config.json`: Individual service configurations
- `services/*/pytest.ini`: Test configuration (where present)