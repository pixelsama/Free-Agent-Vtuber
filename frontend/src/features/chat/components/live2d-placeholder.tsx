import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'

interface Live2DPlaceholderProps {
  readonly className?: string
}

/**
 * Placeholder for the future Live2D canvas, styled to mirror the Figma prototype.
 */
export function Live2DPlaceholder({ className }: Live2DPlaceholderProps = {}) {
  return (
    <Card
      className={cn(
        'flex h-full min-h-[560px] flex-col items-center justify-center rounded-[32px] border-none bg-[#ECE6F0] p-12',
        className
      )}
    >
      <div className="flex flex-1 flex-col items-center justify-center gap-6 text-center text-muted-foreground">
        <Badge
          variant="outline"
          className="rounded-full border-[#CAC4D0] bg-[#FEF7FF] px-3 py-1 text-xs uppercase tracking-wider text-[#625B71]"
        >
          Live2D 区域
        </Badge>
        <div className="grid grid-cols-3 items-center gap-6 text-[#B9B1C3]">
          <div className="h-24 w-24 rounded-3xl bg-current opacity-80" />
          <div className="h-28 w-28 rounded-full border-[6px] border-current/60" />
          <div className="flex h-24 w-24 items-center justify-center rounded-full bg-current/60 text-lg font-semibold text-[#FEF7FF]">
            1st
          </div>
        </div>
        <p className="max-w-[340px] text-sm text-[#625B71]">
          此处将容纳实时 Live2D 模型或场景预览。暂以形状占位，确保布局比例与设计稿一致。
        </p>
      </div>
    </Card>
  )
}
