export function statusBadgeVariant(s: string): 'success' | 'destructive' | 'warning' | 'muted' {
  switch (s) {
    case 'success':
      return 'success'
    case 'failed':
      return 'destructive'
    case 'timeout':
      return 'warning'
    default:
      return 'muted'
  }
}

export function statusForRate(rate: number): string {
  if (rate >= 90) return 'success'
  if (rate >= 70) return 'timeout'
  return 'failed'
}
