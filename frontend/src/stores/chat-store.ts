import { create } from 'zustand'

export type MessageRole = 'user' | 'assistant' | 'system'

export interface ChatMessage {
  readonly id: string
  readonly role: MessageRole
  readonly content: string
  readonly createdAt: number
}

export type UploadStatus = 'idle' | 'connecting' | 'uploading' | 'queued' | 'error'
export type OutputStatus = 'idle' | 'connecting' | 'streaming' | 'completed' | 'error'

interface ChatState {
  readonly taskId: string | null
  readonly messages: ChatMessage[]
  readonly uploadStatus: UploadStatus
  readonly outputStatus: OutputStatus
  readonly audioChunks: Uint8Array[]
  readonly audioUrl: string | null
  readonly lastError: string | null
  setTaskId: (taskId: string | null) => void
  addMessage: (message: ChatMessage) => void
  updateLastMessage: (updater: (message: ChatMessage) => ChatMessage) => void
  setUploadStatus: (status: UploadStatus) => void
  setOutputStatus: (status: OutputStatus) => void
  appendAudioChunk: (chunk: Uint8Array) => void
  finalizeAudio: () => void
  setError: (message: string | null) => void
  reset: () => void
}

function revokeUrl(url: string | null) {
  if (url) URL.revokeObjectURL(url)
}

export const useChatStore = create<ChatState>((set, get) => ({
  taskId: null,
  messages: [],
  uploadStatus: 'idle',
  outputStatus: 'idle',
  audioChunks: [],
  audioUrl: null,
  lastError: null,
  setTaskId: (taskId) => set({ taskId }),
  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),
  updateLastMessage: (updater) =>
    set((state) => {
      if (!state.messages.length) return state
      const lastIndex = state.messages.length - 1
      const nextMessages = [...state.messages]
      nextMessages[lastIndex] = updater(nextMessages[lastIndex])
      return { messages: nextMessages }
    }),
  setUploadStatus: (status) => set({ uploadStatus: status }),
  setOutputStatus: (status) => set({ outputStatus: status }),
  appendAudioChunk: (chunk) =>
    set((state) => ({
      audioChunks: [...state.audioChunks, chunk],
    })),
  finalizeAudio: () => {
    const { audioChunks, audioUrl } = get()
    revokeUrl(audioUrl)
    if (!audioChunks.length) return
    const blob = new Blob(audioChunks, { type: 'audio/mpeg' })
    const url = URL.createObjectURL(blob)
    set({ audioChunks: [], audioUrl: url })
  },
  setError: (message) => set({ lastError: message }),
  reset: () => {
    const { audioUrl } = get()
    revokeUrl(audioUrl)
    set({
      taskId: null,
      messages: [],
      uploadStatus: 'idle',
      outputStatus: 'idle',
      audioChunks: [],
      audioUrl: null,
      lastError: null,
    })
  },
}))

export function createMessage(role: MessageRole, content: string): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    createdAt: Date.now(),
  }
}
