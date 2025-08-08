# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Free-Agent-Vtuber is an event-driven, extensible AI virtual streamer project built with a microservices architecture. The system uses Redis as a message bus for communication between services, allowing for polyglot development (services can be written in any language that can interact with Redis).

### Key Features
- Event-driven microservices architecture with Redis message bus
- Real-time voice-to-text-to-AI-to-speech processing pipeline
- Live2D virtual character integration
- Modular design allowing independent service development
- WebSocket-based real-time communication with frontend

## Architecture Overview

### Core Services
1. **gateway-python** - API gateway routing WebSocket connections to backend services
2. **input-handler-python** - Processes user inputs (text/audio) and forwards to Redis queue
3. **asr-python** - Automatic Speech Recognition service handling voice-to-text conversion
4. **memory-python** - Manages conversation history and context
5. **chat-ai-python** - AI chat processing service generating responses
6. **tts-python** - Text-to-Speech service converting text to audio
7. **output-handler-python** - Sends processed results back to frontend via WebSocket

### Communication Flow
1. Frontend connects to gateway via WebSocket
2. User input (text/audio) sent to input-handler service
3. Input-handler processes data and sends to Redis queue (user_input_queue)
4. Memory service consumes queue, stores context, and publishes updates
5. Chat-AI service listens for memory updates and generates responses
6. TTS service converts text responses to audio
7. Output-handler sends final results back to frontend

### Message Channels
- `user_input_queue` - Main input processing queue
- `memory_updates` - Memory service publishes context updates
- `ai_responses` - AI service publishes generated responses
- `tts_requests` - TTS service consumption queue
- `task_response:{task_id}` - Per-task response channels
- `asr_tasks`/`asr_results` - ASR processing queues

## Development Environment

### Prerequisites
- Python 3.10+
- Node.js 16+
- Redis Server
- Docker & Docker Compose (for containerized deployment)

### Setup
```bash
# Clone repository
git clone <repository-url>
cd Free-Agent-Vtuber

# For Docker deployment (recommended):
cp .env.example .env
# Edit .env to set OPENAI_API_KEY
chmod +x ./deploy.sh
./deploy.sh  # Linux/macOS
# or
deploy.bat   # Windows

# For local development:
# 1. Start Redis server
redis-server

# 2. Set environment variables
export OPENAI_API_KEY=your_api_key_here

# 3. Start manager service
cd manager
pip install -r requirements.txt
python app.py

# 4. In new terminal, start frontend
cd front_end
npm install
npm run dev

# 5. Start individual backend services as needed
# Each service runs independently and connects to Redis
```

### Development Setup
```bash
# Frontend development
cd front_end
npm install
npm run dev     # Development server
npm run build   # Production build
```

For backend service development, each service can be developed independently with its own virtual environment and dependencies.

## Testing

Each service has its own independent test suite located in the `tests/` directory within that service. Tests are organized into unit tests and integration tests.

```bash
# Navigate to a specific service directory
cd services/chat-ai-python

# Run all tests for that service
pytest

# Run specific test types
pytest tests/unit/
pytest tests/integration/

# Run specific test files
pytest tests/unit/test_ai_processor.py

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=. --cov-report=html
```

### Test Structure
- `tests/unit/` - Unit tests for individual components
- `tests/integration/` - Integration tests requiring external services (Redis)
- `conftest.py` - Shared fixtures and configurations

### Requirements
- Redis server running locally for integration tests
- Service-specific dependencies installed via requirements.txt

## Service Development

Each service is developed and run independently:
1. Each service has its own directory under `services/`
2. Each service has its own virtual environment and dependencies
3. Services communicate via Redis queues and pub/sub channels
4. Configuration is managed through individual `config.json` files
5. Each service includes its own test suite in a `tests/` directory

### Adding New Services
1. Create new directory in services/
2. Implement main.py with Redis connection and processing logic
3. Add requirements.txt for dependencies
4. Create config.json for configuration
5. Add Dockerfile for containerization
6. Create tests/ directory with unit and integration tests
7. Update docker-compose.yml to include service

### Service Communication Contracts
Services communicate through well-defined JSON message formats on Redis queues/channels. Each service is responsible for specific processing steps in the pipeline.

## Common Development Tasks

### Running Individual Services
```bash
# Navigate to the specific service directory
cd services/chat-ai-python

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install service dependencies
pip install -r requirements.txt

# Run the service
python main.py
```

Each service can be run independently and communicates with other services through Redis.

### Debugging Message Flow
1. Check service logs through manager UI or direct console output
2. Monitor Redis channels using redis-cli:
   ```bash
   redis-cli
   SUBSCRIBE task_response:your-task-id
   ```

### Testing WebSocket Connections
Use wscat or browser developer tools to test WebSocket endpoints:
- Input: ws://localhost:8000/ws/input
- Output: ws://localhost:8000/ws/output/{task_id}