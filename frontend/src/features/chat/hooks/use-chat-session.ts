import { useCallback, useEffect, useRef, useState } from 'react'

import { buildInputWebSocketUrl, buildOutputWebSocketUrl, buildStopEndpoint } from '@/services/gateway/config'
import { GatewayWebSocketClient } from '@/services/gateway/ws-client'
import { createMessage, type OutputStatus, type UploadStatus, useChatStore } from '@/stores/chat-store'

interface TextMessagePayload {
  readonly content: string
}

interface UseChatSessionReturn {
  readonly isDesktop: boolean
  readonly sendTextMessage: (payload: TextMessagePayload) => Promise<void>
  readonly stopPlayback: () => Promise<void>
  readonly uploadStatus: UploadStatus
  readonly outputStatus: OutputStatus
  readonly lastError: string | null
}

const MIN_DESKTOP_WIDTH = 1024

export function useChatSession(): UseChatSessionReturn {
  const [isDesktop, setIsDesktop] = useState(() => (typeof window === 'undefined' ? false : window.innerWidth >= MIN_DESKTOP_WIDTH))
  const inputClientRef = useRef<GatewayWebSocketClient | null>(null)
  const outputClientRef = useRef<GatewayWebSocketClient | null>(null)

  const {
    taskId,
    uploadStatus,
    outputStatus,
    lastError,
    setTaskId,
    addMessage,
    setUploadStatus,
    setOutputStatus,
    appendAudioChunk,
    finalizeAudio,
    setError,
    reset,
  } = useChatStore(
    ({
      taskId,
      uploadStatus,
      outputStatus,
      lastError,
      setTaskId,
      addMessage,
      setUploadStatus,
      setOutputStatus,
      appendAudioChunk,
      finalizeAudio,
      setError,
      reset,
    }) => ({ taskId, uploadStatus, outputStatus, lastError, setTaskId, addMessage, setUploadStatus, setOutputStatus, appendAudioChunk, finalizeAudio, setError, reset })
  )

  useEffect(() => {
    if (typeof window === 'undefined') return
    const listener = () => setIsDesktop(window.innerWidth >= MIN_DESKTOP_WIDTH)
    window.addEventListener('resize', listener)
    return () => window.removeEventListener('resize', listener)
  }, [])

  const ensureOutputChannel = useCallback(
    (nextTaskId: string) => {
      if (outputClientRef.current) {
        outputClientRef.current.dispose()
      }

      const client = new GatewayWebSocketClient({
        url: buildOutputWebSocketUrl(nextTaskId),
        onOpen: () => {
          setOutputStatus('connecting')
        },
        onMessage: (event) => {
          if (typeof event.data === 'string') {
            handleOutputJson(event.data)
          } else if (event.data instanceof Blob) {
            handleOutputBinary(event.data)
          } else if (event.data instanceof ArrayBuffer) {
            handleOutputBinary(new Blob([event.data]))
          }
        },
        onClose: () => {
          const current = useChatStore.getState().outputStatus
          setOutputStatus(current === 'error' ? 'error' : 'completed')
        },
        onError: () => {
          setOutputStatus('error')
          setError('输出通道连接异常')
        },
      })

      outputClientRef.current = client
      client.connect()
    },
    [setOutputStatus, setError]
  )

  const handleOutputJson = useCallback(
    (payload: string) => {
      try {
        const data = JSON.parse(payload)
        if (data?.status === 'success' && typeof data.content === 'string') {
          addMessage(createMessage('assistant', data.content))
          setOutputStatus(data.audio_present ? 'streaming' : 'completed')
          if (!data.audio_present) {
            finalizeAudio()
          }
        } else if (data?.type === 'audio_chunk') {
          setOutputStatus('streaming')
        } else if (data?.type === 'audio_complete') {
          finalizeAudio()
          setOutputStatus('completed')
        } else if (data?.status === 'error' || data?.type === 'error') {
          setError(data?.error ?? '输出通道错误')
          setOutputStatus('error')
        }
      } catch (error) {
        console.error('Failed to parse output payload', error)
      }
    },
    [addMessage, finalizeAudio, setError, setOutputStatus]
  )

  const handleOutputBinary = useCallback(
    async (blob: Blob) => {
      const arrayBuffer = await blob.arrayBuffer()
      appendAudioChunk(new Uint8Array(arrayBuffer))
    },
    [appendAudioChunk]
  )

  const sendTextMessage = useCallback(
    async ({ content }: TextMessagePayload) => {
      const trimmed = content.trim()
      if (!trimmed) return

      addMessage(createMessage('user', trimmed))
      setUploadStatus('connecting')
      setError(null)

      if (inputClientRef.current) {
        inputClientRef.current.dispose()
      }

      const metadataFrame = {
        action: 'data_chunk',
        type: 'text',
        chunk_id: 0,
      }

      const client = new GatewayWebSocketClient({
        url: buildInputWebSocketUrl(),
        onOpen: () => {
          try {
            client.send(JSON.stringify(metadataFrame))
            client.send(new TextEncoder().encode(trimmed))
            client.send(JSON.stringify({ action: 'upload_complete' }))
            setUploadStatus('uploading')
          } catch (error) {
            console.error(error)
            setError('发送数据失败')
            setUploadStatus('error')
            client.dispose()
          }
        },
        onMessage: (event) => {
          if (typeof event.data !== 'string') return
          try {
            const data = JSON.parse(event.data)
            if (data?.task_id && typeof data.task_id === 'string') {
              setTaskId(data.task_id)
              ensureOutputChannel(data.task_id)
            }
            if (data?.status === 'queued') {
              setUploadStatus('queued')
              client.dispose()
            }
            if (data?.status === 'error') {
              setError(data?.error ?? '输入通道错误')
              setUploadStatus('error')
              client.dispose()
            }
          } catch (error) {
            if (event.data.includes('File chunk received')) {
              setUploadStatus('uploading')
            }
          }
        },
        onClose: () => {
          inputClientRef.current = null
        },
        onError: () => {
          setUploadStatus('error')
          setError('输入通道连接异常')
        },
      })

      inputClientRef.current = client
      client.connect()
    },
    [addMessage, ensureOutputChannel, setError, setTaskId, setUploadStatus]
  )

  const stopPlayback = useCallback(async () => {
    if (!taskId) return
    try {
      const response = await fetch(buildStopEndpoint(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId: taskId }),
      })
      if (!response.ok) {
        const message = await response.text()
        setError(message || '打断请求失败')
      }
    } catch (error) {
      console.error(error)
      setError('打断接口请求失败')
    }
  }, [setError, taskId])

  useEffect(() => {
    return () => {
      inputClientRef.current?.dispose()
      outputClientRef.current?.dispose()
      reset()
    }
  }, [reset])

  return {
    isDesktop,
    sendTextMessage,
    stopPlayback,
    uploadStatus,
    outputStatus,
    lastError,
  }
}
