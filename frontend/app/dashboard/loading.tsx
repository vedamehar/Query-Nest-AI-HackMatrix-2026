import { Skeleton } from "@/components/ui/skeleton"

export default function DashboardLoading() {
  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Header Skeleton */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-10 w-64 rounded-xl bg-white/5" />
          <Skeleton className="h-4 w-48 rounded-lg bg-white/5" />
        </div>
        <Skeleton className="h-12 w-36 rounded-xl bg-brand-purple/20" />
      </div>

      {/* Stats Grid Skeleton */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="glass p-6 rounded-3xl space-y-4 border-white/5">
            <div className="flex items-center justify-between">
              <Skeleton className="h-4 w-24 rounded-lg bg-white/10" />
              <Skeleton className="h-8 w-8 rounded-lg bg-white/10" />
            </div>
            <Skeleton className="h-8 w-16 rounded-lg bg-white/20" />
            <Skeleton className="h-3 w-32 rounded-lg bg-white/5" />
          </div>
        ))}
      </div>

      {/* Main Content Area Skeleton */}
      <div className="glass rounded-3xl p-8 border-white/5 min-h-[400px]">
        <div className="flex items-center justify-between mb-8">
          <Skeleton className="h-8 w-48 rounded-xl bg-white/10" />
          <div className="flex gap-2">
            <Skeleton className="h-10 w-32 rounded-lg bg-white/5" />
            <Skeleton className="h-10 w-10 rounded-lg bg-white/5" />
          </div>
        </div>
        
        <div className="space-y-6">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center gap-4 py-4 border-b border-white/5">
              <Skeleton className="h-12 w-12 rounded-xl bg-white/10 shrink-0" />
              <div className="space-y-2 flex-1">
                <Skeleton className="h-4 w-1/3 rounded-lg bg-white/10" />
                <Skeleton className="h-3 w-1/4 rounded-lg bg-white/5" />
              </div>
              <Skeleton className="h-8 w-24 rounded-lg bg-white/5" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
