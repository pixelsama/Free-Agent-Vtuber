import { useMemo } from 'react'
import { cn } from '@/lib/utils'
import { Menu, MoreVertical, UserCircle2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useChatSession } from '@/features/chat/hooks/use-chat-session'
import { useChatStore } from '@/stores/chat-store'

import { MessageComposer } from './message-composer'
import { MessageBubble } from './message-bubble'

interface ChatShellProps {
  readonly className?: string
}

export function ChatShell({ className }: ChatShellProps = {}) {
  const messages = useChatStore((state) => state.messages)
  const audioUrl = useChatStore((state) => state.audioUrl)
  const { stopPlayback, uploadStatus, outputStatus, lastError } = useChatSession()

  const groupedMessages = useMemo(() => {
    return messages.map((message) => ({
      ...message,
      timestamp: new Date(message.createdAt).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      }),
    }))
  }, [messages])

  return (
    <div className={cn('flex min-h-[520px] flex-1 flex-col rounded-lg bg-[#F7F2FA]', className)}>
      <div className="flex items-center justify-between rounded-t-lg bg-[#F0E7F7] px-6 py-4">
        <div className="flex items-center gap-4">
          <Button size="icon" variant="ghost" className="h-9 w-9 rounded-full text-[#625B71] hover:bg-[#E8DEF8]">
            <Menu className="h-5 w-5" />
          </Button>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-[#1D1B20]">桃汐</h2>
              <Badge className="rounded-full bg-[#E8DEF8] px-2 py-0 text-xs text-[#49454F]">在线</Badge>
            </div>
            <p className="text-xs text-[#625B71]">
              {uploadStatus === 'uploading' || uploadStatus === 'queued' ? '上传中…' : '实时对话 · 流式输出'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button size="icon" variant="ghost" className="h-9 w-9 rounded-full text-[#625B71] hover:bg-[#E8DEF8]">
                <UserCircle2 className="h-5 w-5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>资料设置</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button size="icon" variant="ghost" className="h-9 w-9 rounded-full text-[#625B71] hover:bg-[#E8DEF8]">
                <MoreVertical className="h-5 w-5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>更多操作</TooltipContent>
          </Tooltip>
          <Button
            size="sm"
            variant="ghost"
            className="rounded-md text-xs text-[#625B71] hover:bg-[#E8DEF8]"
            onClick={() => stopPlayback()}
          >
            打断播放
          </Button>
        </div>
      </div>

      <Separator className="bg-[#E3DAEE]" />

      <div className="flex flex-1 flex-col overflow-hidden">
        <ScrollArea className="h-full flex-1 px-6 py-6">
          <div className="flex flex-col gap-6">
            {groupedMessages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
          </div>
        </ScrollArea>
        <Separator className="bg-[#E3DAEE]" />
        <div className="px-6 pb-6 pt-4">
          <MessageComposer />
          {lastError ? <p className="mt-3 rounded-md bg-red-100 px-3 py-2 text-xs text-red-700">{lastError}</p> : null}
          <p className="mt-2 text-xs text-[#625B71]">
            输出状态：{outputStatus === 'streaming' ? '播放中' : outputStatus === 'completed' ? '已完成' : outputStatus === 'error' ? '出错' : '待机'}
          </p>
          {audioUrl ? (
            <audio src={audioUrl} controls className="mt-3 w-full" />
          ) : null}
        </div>
      </div>
    </div>
  )
}
