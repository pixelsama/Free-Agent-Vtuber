import { ChatShell } from '@/features/chat/components/chat-shell'
import { Live2DPlaceholder } from '@/features/chat/components/live2d-placeholder'

export function ChatHomePage() {
  return (
    <section className="flex min-h-screen flex-col gap-6 px-6 py-10 lg:flex-row">
      <div className="mx-auto w-full max-w-[360px] lg:mx-0">
        <ChatShell />
      </div>
      <div className="flex flex-1">
        <Live2DPlaceholder className="flex-1" />
      </div>
    </section>
  )
}
