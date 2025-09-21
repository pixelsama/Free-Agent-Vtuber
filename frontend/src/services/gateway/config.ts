const DEFAULT_GATEWAY_PORT = 8000

export function resolveGatewayBaseUrl() {
  const configured = import.meta.env.VITE_GATEWAY_URL
  if (configured) {
    return configured.replace(/\/$/, '')
  }

  const { protocol, hostname } = window.location
  const normalizedProtocol = protocol === 'https:' ? 'wss:' : 'ws:'
  return `${normalizedProtocol}//${hostname}:${DEFAULT_GATEWAY_PORT}`
}

export function buildInputWebSocketUrl() {
  return `${resolveGatewayBaseUrl()}/ws/input`
}

export function buildOutputWebSocketUrl(taskId: string) {
  return `${resolveGatewayBaseUrl()}/ws/output/${taskId}`
}

export function buildStopEndpoint() {
  const httpProtocol = window.location.protocol === 'https:' ? 'https:' : 'http:'
  const hostname = window.location.hostname
  const port = import.meta.env.VITE_GATEWAY_HTTP_PORT ?? '8000'
  return `${httpProtocol}//${hostname}:${port}/control/stop`
}
