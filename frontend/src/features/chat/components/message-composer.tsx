import { useLayoutEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode, RefObject } from 'react'
import { AudioLines, Plane, Plus } from 'lucide-react'

import { Textarea } from '@/components/ui/textarea'
import { useChatSession } from '@/features/chat/hooks/use-chat-session'

export function MessageComposer() {
  const [draft, setDraft] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const { sendTextMessage } = useChatSession()

  useAutoResize(textareaRef, draft)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmed = draft.trim()
    if (!trimmed) return

    await sendTextMessage({ content: trimmed })
    setDraft('')
  }

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
        <IconCircle label="添加附件" variant="ghost" className="rounded-lg">
          <Plus className="h-4 w-4" />
        </IconCircle>
        <div className="flex min-h-[64px] flex-1 items-center gap-3 rounded-lg border border-[#DED6EA] bg-[#F0E8F7] px-4 py-2">
          <Textarea
            ref={textareaRef}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            rows={1}
            aria-label="输入消息"
            className="max-h-20 min-h-[28px] flex-1 resize-none border-none bg-transparent px-0 py-1 text-[16px] text-[#1D1B20] leading-[1.5] shadow-none focus-visible:ring-0"
          />
          <div className="flex items-center gap-2">
            <IconCircle label="语音输入" className="rounded-lg">
              <AudioLines className="h-4 w-4" />
            </IconCircle>
            <button
              type="submit"
              disabled={!draft.trim()}
              aria-label="发送"
              className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-[#CAC4D0] bg-[#625B71] text-white transition hover:bg-[#514760] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#625B71]/40 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Plane className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </form>
  )
}

function useAutoResize(ref: RefObject<HTMLTextAreaElement | null>, value: string) {
  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, 96)}px`
  }, [ref, value])
}

interface IconCircleProps {
  readonly children: ReactNode
  readonly label: string
  readonly className?: string
  readonly variant?: 'ghost' | 'default'
}

function IconCircle({ children, label, className, variant = 'default' }: IconCircleProps) {
  const baseClasses =
    'inline-flex h-11 w-11 items-center justify-center rounded-lg border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#625B71]/40'
  const palette =
    variant === 'ghost'
      ? 'border-[#CAC4D0] bg-[#FEF7FF] text-[#625B71] hover:bg-[#E8DEF8]'
      : 'border-[#DACFE6] bg-[#F7F2FA] text-[#625B71] hover:bg-[#E8DEF8]'

  return (
    <button type="button" aria-label={label} className={`${baseClasses} ${palette} ${className ?? ''}`}>
      {children}
    </button>
  )
}
