import { memo } from 'react'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'
import type { ChatMessage } from '@/stores/chat-store'

interface MessageBubbleProps {
  readonly message: ChatMessage & { timestamp?: string }
}

export const MessageBubble = memo(({ message }: MessageBubbleProps) => {
  const isUser = message.role === 'user'
  const alignment = isUser ? 'items-end text-right' : 'items-start text-left'
  const bubbleClasses = cn(
    'max-w-[220px] rounded-[22px] px-5 py-3 text-sm shadow-sm transition-colors sm:max-w-[260px] sm:text-base',
    isUser
      ? 'rounded-tr-[8px] bg-[#625B71] text-[#FFFFFF]'
      : 'rounded-tl-[8px] bg-[#E8DEF8] text-[#1D1B20]'
  )

  return (
    <div className={cn('flex w-full gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}>
      <Avatar className="mt-1 h-8 w-8 bg-[#F7F2FA] text-[#625B71]">
        <AvatarFallback className="text-xs font-semibold">
          {isUser ? '我' : '桃'}
        </AvatarFallback>
      </Avatar>
      <div className={cn('flex flex-col gap-2', alignment)}>
        <div className={bubbleClasses}>{message.content}</div>
        <span className="text-xs uppercase tracking-[0.18em] text-[#7A7289]">
          {message.timestamp}
        </span>
      </div>
    </div>
  )
})
MessageBubble.displayName = 'MessageBubble'
