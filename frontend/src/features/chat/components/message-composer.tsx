import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { AudioLines, Laugh, Plus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useChatStore } from '@/stores/chat-store'

export function MessageComposer() {
  const [draft, setDraft] = useState('')
  const addMessage = useChatStore((state) => state.addMessage)

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmed = draft.trim()
    if (!trimmed) return

    addMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
      createdAt: Date.now(),
    })
    setDraft('')
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="flex items-end gap-3 rounded-[28px] bg-[#E6E0EE] px-4 py-4 shadow-inner">
        <IconPill label="添加附件">
          <Plus className="h-4 w-4" />
        </IconPill>
        <IconPill label="插入表情">
          <Laugh className="h-4 w-4" />
        </IconPill>
        <Textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="开始输入或粘贴指令，Shift + Enter 换行"
          rows={2}
          className="flex-1 resize-none border-none bg-transparent px-1 text-base text-[#1D1B20] shadow-none focus-visible:ring-0"
        />
        <IconPill label="文本模式" className="px-3">
          <span className="text-sm font-medium">Tt</span>
        </IconPill>
        <IconPill label="语音输入">
          <AudioLines className="h-4 w-4" />
        </IconPill>
        <Button type="submit" disabled={!draft.trim()} className="ml-1 h-10 rounded-full bg-[#625B71] px-6 text-sm font-semibold text-white">
          发送
        </Button>
      </div>
    </form>
  )
}

interface IconPillProps {
  readonly children: ReactNode
  readonly label: string
  readonly className?: string
}

function IconPill({ children, label, className }: IconPillProps) {
  return (
    <button
      type="button"
      aria-label={label}
      className={`inline-flex h-10 min-w-[40px] items-center justify-center rounded-full bg-[#F7F2FA] text-[#625B71] transition hover:bg-[#E8DEF8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#625B71]/40 ${className ?? ''}`}
    >
      {children}
    </button>
  )
}
