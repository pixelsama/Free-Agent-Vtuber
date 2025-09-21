import { ChatShell } from '@/features/chat/components/chat-shell'
import { Live2DPlaceholder } from '@/features/chat/components/live2d-placeholder'

export function ChatHomePage() {
  return (
    <section className="grid gap-6 px-6 py-8 lg:grid-cols-[320px_minmax(0,1fr)]">
      <ChatShell />
      <Live2DPlaceholder />
    </section>
  )
}
