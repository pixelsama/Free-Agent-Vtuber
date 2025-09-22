import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'

interface Live2DPlaceholderProps {
  readonly className?: string
}

/**
 * Placeholder for the future Live2D canvas，采用扁平矩形布局以便替换为真实渲染区域。
 */
export function Live2DPlaceholder({ className }: Live2DPlaceholderProps = {}) {
  return (
    <div
      className={cn(
        'flex h-full min-h-[560px] flex-1 flex-col rounded-lg bg-[#E8E1F2] p-12',
        className
      )}
    >
      <div className="flex flex-1 flex-col items-center justify-center gap-6 text-center text-muted-foreground">
        <Badge
          variant="outline"
          className="rounded-md border-[#CAC4D0] bg-[#F6F0FA] px-3 py-1 text-xs uppercase tracking-wider text-[#625B71]"
        >
          Live2D 区域
        </Badge>
        <div className="grid grid-cols-3 items-center gap-6 text-[#B9B1C3]">
          <div className="h-24 w-24 rounded-xl bg-current opacity-80" />
          <div className="h-28 w-28 rounded-full border-[6px] border-current/60" />
          <div className="flex h-24 w-24 items-center justify-center rounded-full bg-current/60 text-lg font-semibold text-[#FEF7FF]">
            1st
          </div>
        </div>
        <p className="max-w-[360px] text-sm text-[#625B71]">
          此处将容纳实时 Live2D 模型或场景预览。暂以形状占位，确保布局比例与设计稿一致。
        </p>
      </div>
    </div>
  )
}
