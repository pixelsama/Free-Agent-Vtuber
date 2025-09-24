# Mem0 Provider Environment Quick Reference

This guide summarises the environment variables you may need when switching the
long-term memory service to different Mem0 providers. The information is based
on the latest Mem0 documentation (Context7 `/mem0ai/mem0`, sections "Supported
LLM Providers" and "Supported Embedding Providers"). Any provider on those
lists can be used; the table below covers the ones we expect operators to reach
for most often.

> Tip: keep secrets in your preferred secret manager or Docker/Compose `.env`
overrides instead of editing tracked files.

## Core Variables

| Purpose                | Variable                     | Notes |
|------------------------|------------------------------|-------|
| Mem0 API key (Cloud)   | `MEM0_API_KEY`               | Required for Mem0 Cloud users. Not needed for self-hosted Mem0. |
| Base config path       | `MEM0_CONFIG_PATH`           | Defaults to `config/mem0_config.yaml`. Set when mounting a custom config. |
| LLM provider override  | `MEM0_LLM_PROVIDER`          | Will be consumed once Phase 2 introduces runtime overrides. |
| LLM config JSON        | `MEM0_LLM_CONFIG_JSON`       | JSON string with provider-specific options (Phase 2+). |
| Embedder provider      | `MEM0_EMBEDDER_PROVIDER`     | Used together with `MEM0_LLM_PROVIDER`. |
| Embedder config JSON   | `MEM0_EMBEDDER_CONFIG_JSON`  | JSON string with embedder options (Phase 2+). |

## Configuration Schema

Overrides flow straight into the `llm` / `embedder` blocks that Mem0 expects.
The service merges JSON snippets with the YAML defaults, so any provider listed
in the official Mem0 matrix can be configured as follows:

```json
{
  "llm": {
    "provider": "<provider-name>",
    "config": {
      "model": "<model-id>",
      "api_key": "...",
      "base_url": "..."
    }
  },
  "embedder": {
    "provider": "<provider-name>",
    "config": {
      "model": "<embedding-model>",
      "...": "..."
    }
  }
}
```

`MEM0_LLM_PROVIDER` / `MEM0_EMBEDDER_PROVIDER` set the `provider` fields, while
the `*_CONFIG_JSON` variables merge into the nested `config` objects. Any keys
allowed by Mem0 (for example `ollama_base_url`, `deepseek_base_url`,
`aws_region`) can be supplied.

## Provider Highlights

| Provider   | Scope     | Required Variables / Notes |
|------------|-----------|-----------------------------|
| OpenAI     | LLM + Emb | `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, choose model via `MEM0_LLM_CONFIG_JSON` (e.g. `{ "model": "gpt-4o-mini" }`). |
| Anthropic  | LLM       | `ANTHROPIC_API_KEY`; Mem0 config expects model name such as `claude-3-5-sonnet-20240620`. |
| Gemini     | LLM/Emb   | `GOOGLE_API_KEY`; specify `model` (e.g. `models/gemini-1.5-pro-latest` for LLM or `models/text-embedding-004` for embeddings). |
| DeepSeek   | LLM       | `DEEPSEEK_API_KEY` and optionally `DEEPSEEK_BASE_URL` for self-hosted gateways. |
| xAI        | LLM       | `XAI_API_KEY`; include `xai_api_base` if using a non-default endpoint. |
| Azure OpenAI | LLM/Emb | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`. Mem0 supports both text and embedding deployments. |
| AWS Bedrock | LLM/Emb  | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and region variables recognised by the AWS SDK. Model IDs go into the Mem0 config JSON. |
| Groq       | LLM       | `GROQ_API_KEY`; typical models include `mixtral-8x7b-32768`. |
| Together   | LLM/Emb   | `TOGETHER_API_KEY`; specify `model` in the config JSON. |
| HuggingFace | Emb      | `HUGGINGFACEHUB_API_TOKEN` (if using gated models); set `model` to desired transformer name. |
| Ollama     | LLM/Emb   | No API key. Ensure `OLLAMA_HOST` or include `ollama_base_url` in the config JSON (default `http://localhost:11434`). |
| LM Studio  | LLM/Emb   | No API key. Provide the local server URL via `LMSTUDIO_BASE_URL` (default `http://localhost:1234`). |
| Vertex AI  | Emb       | `GOOGLE_APPLICATION_CREDENTIALS` pointing to a service account JSON; configure `model` such as `text-embedding-004`. |

## Example Snippets

### OpenAI (default)

```
export OPENAI_API_KEY="sk-..."
export MEM0_LLM_PROVIDER="openai"
export MEM0_LLM_CONFIG_JSON='{"model": "gpt-4o-mini", "temperature": 0.1}'
export MEM0_EMBEDDER_PROVIDER="openai"
export MEM0_EMBEDDER_CONFIG_JSON='{"model": "text-embedding-3-small"}'
```

### Anthropic + OpenAI Embeddings

```
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-openai-..."
export MEM0_LLM_PROVIDER="anthropic"
export MEM0_LLM_CONFIG_JSON='{"model": "claude-3-5-sonnet-20240620"}'
export MEM0_EMBEDDER_PROVIDER="openai"
export MEM0_EMBEDDER_CONFIG_JSON='{"model": "text-embedding-3-small"}'
```

### Local Ollama

```
export MEM0_LLM_PROVIDER="ollama"
export MEM0_LLM_CONFIG_JSON='{"model": "llama3.1", "ollama_base_url": "http://localhost:11434"}'
export MEM0_EMBEDDER_PROVIDER="ollama"
export MEM0_EMBEDDER_CONFIG_JSON='{"model": "all-minilm:latest", "ollama_base_url": "http://localhost:11434"}'
```

### LM Studio LLM + Gemini Embeddings

```
export LMSTUDIO_BASE_URL="http://localhost:1234"
export MEM0_LLM_PROVIDER="lmstudio"
export MEM0_LLM_CONFIG_JSON='{"model": "lmstudio-community/Qwen2.5-7B-Instruct", "base_url": "http://localhost:1234"}'
export GOOGLE_API_KEY="..."
export MEM0_EMBEDDER_PROVIDER="gemini"
export MEM0_EMBEDDER_CONFIG_JSON='{"model": "models/text-embedding-004"}'
```

Keep this document alongside `docs/ltm-multi-provider-plan.md` and update it
whenever new providers are adopted or Mem0 introduces additional configuration
options.
