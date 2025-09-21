import { useMemo } from 'react'
import { Menu, MoreVertical, UserCircle2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useChatStore } from '@/stores/chat-store'

import { MessageComposer } from './message-composer'
import { MessageBubble } from './message-bubble'

export function ChatShell() {
  const messages = useChatStore((state) => state.messages)

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
    <Card className="flex h-full min-h-[520px] flex-col rounded-[32px] border-[3px] border-[#E6E0EE] bg-[#FFFFFF] shadow-[0px_20px_36px_rgba(98,91,113,0.08)]">
      <div className="flex items-center justify-between rounded-t-[28px] bg-[#FEF7FF] px-6 py-4">
        <div className="flex items-center gap-4">
          <Button size="icon" variant="ghost" className="h-9 w-9 rounded-full text-[#625B71] hover:bg-[#E8DEF8]">
            <Menu className="h-5 w-5" />
          </Button>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-[#1D1B20]">桃汐</h2>
              <Badge className="rounded-full bg-[#E8DEF8] px-2 py-0 text-xs text-[#49454F]">在线</Badge>
            </div>
            <p className="text-xs text-[#625B71]">实时对话 · 流式输出</p>
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
        </div>
      </div>

      <Separator className="bg-[#E6E0EE]" />

      <div className="flex flex-1 flex-col overflow-hidden">
        <ScrollArea className="h-full flex-1 px-6 py-6">
          <div className="flex flex-col gap-6">
            {groupedMessages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
          </div>
        </ScrollArea>
        <Separator className="bg-[#E6E0EE]" />
        <div className="px-6 pb-6 pt-4">
          <MessageComposer />
        </div>
      </div>
    </Card>
  )
}
