/**
 * dateUtils — utilitários de data reutilizáveis no portal HQ.
 * Padrão: "ha X dias", "ha X horas", "agora"
 */

/**
 * Formata data como string relativa em português.
 * Ex: "ha 2h", "ha 3 dias", "agora"
 */
export function formatRelative(dateStr: string): string {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffMs = now - then

  if (diffMs < 0) return 'agora'
  if (diffMs < 60_000) return 'agora'
  if (diffMs < 3_600_000) {
    const mins = Math.floor(diffMs / 60_000)
    return `ha ${mins}min`
  }
  if (diffMs < 86_400_000) {
    const hours = Math.floor(diffMs / 3_600_000)
    return `ha ${hours}h`
  }
  const days = Math.floor(diffMs / 86_400_000)
  return `ha ${days} ${days === 1 ? 'dia' : 'dias'}`
}

/**
 * Formata data como string absoluta no padrão brasileiro.
 * Ex: "06/04/2026 14:32"
 */
export function formatAbsolute(dateStr: string): string {
  const d = new Date(dateStr)
  const day = String(d.getDate()).padStart(2, '0')
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const year = d.getFullYear()
  const hours = String(d.getHours()).padStart(2, '0')
  const mins = String(d.getMinutes()).padStart(2, '0')
  return `${day}/${month}/${year} ${hours}:${mins}`
}
