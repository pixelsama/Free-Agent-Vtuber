export interface GatewayWebSocketClientOptions {
  readonly url: string
  readonly protocols?: string | string[]
  readonly onOpen?: (event: Event) => void
  readonly onMessage?: (event: MessageEvent) => void
  readonly onError?: (event: Event) => void
  readonly onClose?: (event: CloseEvent) => void
  readonly WebSocketImpl?: typeof WebSocket
}

/**
 * A lightweight wrapper around the browser WebSocket for gateway interactions.
 * This creates a seam that we can extend with reconnection logic in later iterations.
 */
export class GatewayWebSocketClient {
  private socket?: WebSocket
  private readonly options: GatewayWebSocketClientOptions

  constructor(options: GatewayWebSocketClientOptions) {
    this.options = options
  }

  connect() {
    this.dispose()
    const { WebSocketImpl = WebSocket } = this.options
    this.socket = new WebSocketImpl(this.options.url, this.options.protocols)
    this.attachEventListeners(this.socket)
    return this.socket
  }

  send(data: string | ArrayBufferLike | Blob | ArrayBufferView) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      throw new Error('Attempted to send data on a closed WebSocket connection.')
    }
    this.socket.send(data)
  }

  dispose() {
    if (this.socket) {
      this.socket.close()
      this.detachEventListeners(this.socket)
      this.socket = undefined
    }
  }

  get readyState() {
    return this.socket?.readyState ?? WebSocket.CLOSED
  }

  private attachEventListeners(socket: WebSocket) {
    if (this.options.onOpen) socket.addEventListener('open', this.options.onOpen)
    if (this.options.onMessage) socket.addEventListener('message', this.options.onMessage)
    if (this.options.onError) socket.addEventListener('error', this.options.onError)
    if (this.options.onClose) socket.addEventListener('close', this.options.onClose)
  }

  private detachEventListeners(socket: WebSocket) {
    if (this.options.onOpen) socket.removeEventListener('open', this.options.onOpen)
    if (this.options.onMessage) socket.removeEventListener('message', this.options.onMessage)
    if (this.options.onError) socket.removeEventListener('error', this.options.onError)
    if (this.options.onClose) socket.removeEventListener('close', this.options.onClose)
  }
}
