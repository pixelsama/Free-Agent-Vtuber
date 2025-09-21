import { create } from 'zustand'

export type MessageRole = 'user' | 'assistant' | 'system'

export interface ChatMessage {
  readonly id: string
  readonly role: MessageRole
  readonly content: string
  readonly createdAt: number
}

const seededMessages: ChatMessage[] = [
  {
    id: 'seed-user-1',
    role: 'user',
    content: 'or we could make this?',
    createdAt: Date.now() - 1000 * 60 * 3,
  },
  {
    id: 'seed-assistant-1',
    role: 'assistant',
    content: 'that looks so good!',
    createdAt: Date.now() - 1000 * 60 * 2,
  },
]

interface ChatState {
  readonly taskId: string | null
  readonly messages: ChatMessage[]
  readonly isStreaming: boolean
  setTaskId: (taskId: string | null) => void
  addMessage: (message: ChatMessage) => void
  updateLastMessage: (updater: (message: ChatMessage) => ChatMessage) => void
  setStreaming: (value: boolean) => void
  reset: () => void
}

export const useChatStore = create<ChatState>((set) => ({
  taskId: null,
  messages: seededMessages,
  isStreaming: false,
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
  setStreaming: (value) => set({ isStreaming: value }),
  reset: () => set({ taskId: null, messages: seededMessages, isStreaming: false }),
}))
