import { useEffect, useMemo, useRef, useState } from 'react'

import { ChatShell } from '@/features/chat/components/chat-shell'
import { Live2DPlaceholder } from '@/features/chat/components/live2d-placeholder'

const DESKTOP_BREAKPOINT = 1024
const MIN_CHAT_WIDTH = 280
const MIN_LIVE2D_WIDTH = 420

export function ChatHomePage() {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const dragContext = useRef<{ containerLeft: number; containerWidth: number } | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [chatWidth, setChatWidth] = useState(360)
  const [isDesktop, setIsDesktop] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const update = () => {
      const width = window.innerWidth
      setIsDesktop(width >= DESKTOP_BREAKPOINT)
      if (width < DESKTOP_BREAKPOINT) {
        setChatWidth(360)
      }
    }
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  useEffect(() => {
    if (!isDragging) return

    const handlePointerMove = (event: PointerEvent) => {
      const context = dragContext.current
      if (!context) return
      const { containerLeft, containerWidth } = context
      const proposedWidth = event.clientX - containerLeft
      const maxChatWidth = containerWidth - MIN_LIVE2D_WIDTH
      const clamped = Math.max(MIN_CHAT_WIDTH, Math.min(proposedWidth, Math.max(maxChatWidth, MIN_CHAT_WIDTH)))
      setChatWidth(clamped)
    }

    const handlePointerUp = () => {
      setIsDragging(false)
      dragContext.current = null
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', handlePointerUp)
    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', handlePointerUp)
    }
  }, [isDragging])

  const handleDragStart = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!isDesktop || !containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    dragContext.current = { containerLeft: rect.left, containerWidth: rect.width }
    setIsDragging(true)
    event.preventDefault()
  }

  const chatPaneStyle = useMemo(() => {
    if (!isDesktop) return undefined
    return { flexBasis: `${chatWidth}px`, maxWidth: `${chatWidth}px` }
  }, [chatWidth, isDesktop])

  return (
    <section ref={containerRef} className="flex min-h-screen flex-col lg:flex-row">
      <div className="flex w-full flex-1" style={chatPaneStyle}>
        <ChatShell className="h-full border-r border-[#DED6EA]" />
      </div>
      <div
        className="hidden w-2 cursor-col-resize items-stretch bg-transparent lg:flex"
        onPointerDown={handleDragStart}
      >
        <span className={`mx-auto w-[2px] rounded-full transition-colors ${isDragging ? 'bg-[#C2B5DB]' : 'bg-transparent hover:bg-[#D7CEE9]'}`} />
      </div>
      <div className="flex flex-1">
        <Live2DPlaceholder className="flex-1" />
      </div>
    </section>
  )
}
