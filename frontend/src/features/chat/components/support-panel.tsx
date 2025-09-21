import type { ComponentType } from 'react'
import { Lightbulb, Rocket, Settings2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'

const quickActions = [
  {
    icon: Lightbulb,
    title: '灵感激发',
    description: '获取对话开场、故事灵感或直播脚本草稿。',
  },
  {
    icon: Rocket,
    title: '场景预设',
    description: '直接加载“直播”、“歌回”、“陪聊”等复杂场景配置。',
  },
  {
    icon: Settings2,
    title: '实时调优',
    description: '微调语气、情绪权重与播报速度，随时同步后端配置。',
  },
] satisfies ActionItemProps[]

export function SupportPanel() {
  return (
    <div className="flex h-full min-h-[580px] flex-col gap-4">
      <Card className="border-none bg-card/70 shadow-lg">
        <CardHeader className="space-y-2">
          <Badge variant="secondary" className="w-fit rounded-full px-2 py-0.5 text-[11px]">
            体验版本
          </Badge>
          <CardTitle className="text-2xl">智能对话驱动</CardTitle>
          <p className="text-sm text-muted-foreground">
            以上传语音/文本为起点，组合流式 TTS 与打断控制，打造更拟真互动体验。
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <ScrollArea className="max-h-72 pr-4">
            <div className="flex flex-col gap-4">
              {quickActions.map((action) => (
                <ActionItem key={action.title} {...action} />
              ))}
            </div>
          </ScrollArea>
          <Button variant="secondary" className="w-full">
            查看接口契约
          </Button>
        </CardContent>
      </Card>
      <Card className="flex-1 border-none bg-card/40 shadow-inner">
        <CardContent className="flex h-full flex-col items-center justify-center gap-3 text-center text-muted-foreground">
          <span className="text-sm uppercase tracking-[0.2em]">设计稿预览位</span>
          <p className="max-w-[220px] text-sm">
            后续将嵌入 Figma 轮播、运行状态摘要或直播场景卡片，辅助主要对话区。
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

interface ActionItemProps {
  readonly icon: ComponentType<{ className?: string }>
  readonly title: string
  readonly description: string
}

function ActionItem({ icon: Icon, title, description }: ActionItemProps) {
  return (
    <div className="flex gap-3 rounded-2xl border border-border/60 bg-background/80 p-4 shadow-sm">
      <div className="mt-1 flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  )
}
