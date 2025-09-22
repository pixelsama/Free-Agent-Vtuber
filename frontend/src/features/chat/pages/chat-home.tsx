import { ChatShell } from '@/features/chat/components/chat-shell'
import { Live2DPlaceholder } from '@/features/chat/components/live2d-placeholder'

export function ChatHomePage() {
  return (
    <section className="flex min-h-screen flex-col gap-0 lg:flex-row">
      <div className="flex w-full max-w-[360px] flex-1">
        <ChatShell className="h-full border-r border-[#DED6EA]" />
      </div>
      <div className="flex flex-1">
        <Live2DPlaceholder className="flex-1" />
      </div>
    </section>
  )
}
