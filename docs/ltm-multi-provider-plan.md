# Long-Term Memory Multi-Provider Enablement Plan

## 1. Goals
- Let the Mem0-backed long-term memory (LTM) service run against the full set of LLM providers supported by Mem0 (19 options such as OpenAI, Anthropic, Gemini, DeepSeek, xAI, Ollama, LM Studio, Groq, Bedrock, Azure OpenAI, etc.).
- Offer embedding provider flexibility across all Mem0-supported embedders (10 options, e.g. OpenAI, HuggingFace, Gemini, Ollama, LM Studio, Vertex AI, Together, Bedrock, Azure OpenAI).
- Keep configuration driven and easy to override so deployers can pick providers per environment without editing source files.
- Preserve existing Redis queue interfaces and response payloads.

## 2. Reference: Mem0 Provider Matrix
The latest Mem0 documentation (Context7 `/mem0ai/mem0`, sections "Supported LLM Providers" and "Supported Embedding Providers") enumerates 19 LLM backends and 10 embedding backends. Rather than narrowing that list, we plan to expose configuration hooks so the LTM service can leverage **any** provider Mem0 supports. Mem0 already exposes provider-specific configuration blocks (`llm.config` and `embedder.config`) with keys such as `model`, `api_key`, `temperature`, `base_url`, or provider-specific parameters (`ollama_base_url`, `deepseek_base_url`, etc.). Our work is to surface these options in a user-friendly way.

## 3. Current State Snapshot
- `services/long-term-memory-python/config/config.json` pins the LTM service to OpenAI LLM + pgvector via `/app/config/mem0_config.yaml`.
- `config/mem0_config.yaml` only describes OpenAI for both LLM and embeddings.
- `Mem0Service` (`src/core/mem0_client.py`) loads a single config path and does not expose a way to override provider settings at runtime.
- Environment management (`ConfigLoader`) offers a single `MEM0_CONFIG_PATH` override; no fine-grained toggles per provider.
- Tests rely on mocked `Memory.from_config`, so adding providers should not break unit suites if the configuration surface is backward compatible.

## 4. Implementation Plan
### Phase 1 — Configuration Refactor
1. Replace `config/mem0_config.yaml` with a template that separates provider-agnostic defaults from provider-specific examples.
2. Introduce a new `docs/env-mem0-providers.md` or enrich `.env.example` to document the required environment variables for representative providers (API keys, base URLs) while explaining how to extend to any other Mem0 provider.
3. Extend the JSON config (`config/config.json`) to include optional maps, e.g.:
   ```json
   "mem0": {
     "config_path": "/app/config/mem0_config.yaml",
     "llm_provider": "openai",
     "embedding_provider": "openai"
   }
   ```
   These keys allow the service to select a provider without hand-editing the YAML.

### Phase 2 — Dynamic Mem0 Client Initialization
1. Update `Mem0Service._ensure_client` to merge runtime overrides before calling `Memory.from_config`:
   - Load the base YAML/JSON config.
   - Overlay `llm.provider`, `embedder.provider`, and their `config` dictionaries if environment variables or JSON fields specify them.
2. Accept provider-specific JSON payloads via environment variables, e.g. `MEM0_LLM_CONFIG_JSON` and `MEM0_EMBEDDER_CONFIG_JSON`, to avoid duplicating YAML files for each provider.
3. Validate that the selected providers are in the Mem0-supported list (helpful error messages) and design the validation to stay aligned with future Mem0 releases.

### Phase 3 — Provider-Specific Support
1. Surface a generic configuration schema that maps directly onto Mem0's `llm` and `embedder` blocks (provider string + arbitrary nested `config`), avoiding hard-coded branches per provider in application code.
2. Provide documentation tables that list common providers (OpenAI, Anthropic, Gemini, DeepSeek, xAI, Ollama, LM Studio, Groq, AWS Bedrock, Azure OpenAI, Together, etc.) with their required keys/base URLs, while clarifying that any other Mem0 provider can be supplied using the same mechanism.
3. Update Docker Compose and `.env.example` with representative environment variable placeholders (e.g. `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `MEM0_OLLAMA_BASE_URL`, `AWS_ACCESS_KEY_ID`, `GOOGLE_API_KEY`) and guidance on extending the list as needed.

### Phase 4 — Testing & Validation
1. Expand unit tests to cover configuration merging logic (mock `Memory.from_config` to assert correct provider injection).
2. Add parametrized tests for each provider override to ensure no key collisions.
3. Spin up selective integration checks using local providers where feasible:
   - Ollama + LM Studio have local stories; provide manual instructions in the docs for developers.
4. Ensure existing tests remain green (mock-based). Where network calls are impossible, confirm exceptions surface clear "missing API key" messages.

### Phase 5 — Documentation & Rollout
1. Write operator documentation (in `docs/`) explaining how to enable each provider with sample environment blocks and expected prerequisites.
2. Update changelog / release notes highlighting multi-provider capability.
3. Coordinate with DevOps to provision secrets (Anthropic, DeepSeek, xAI) and to expose required ports for local providers.

## 5. Risk & Mitigations
- **Misconfiguration**: Mitigate by validating provider names against the Mem0 supported set and logging helpful tips.
- **Secret sprawl**: Centralize environment variable names, encourage secret managers rather than files.
- **Local provider latency / availability**: For Ollama or LM Studio, document health checks and timeouts inside the service.
- **Inconsistent embedding dimensions**: When switching models, ensure downstream vector store (pgvector) accepts matching dimensions; plan schema migration or dynamic column sizing if needed.

## 6. Deliverables
- Updated configuration artifacts (`config.json`, `mem0_config.yaml`, `.env.example`, Docker compose environment section).
- Enhanced `Mem0Service` initialization with provider injection and validation.
- Tests covering configuration pathways.
- Documentation for operators and developers (this plan + provider setup guide).
