import { useEffect, useRef } from 'react'

interface RiskGaugeProps {
  score: number
  size?: number
  label?: string
}

export function RiskGauge({ score, size = 120, label = 'Live Risk' }: RiskGaugeProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    canvas.width = size * dpr
    canvas.height = size * dpr
    ctx.scale(dpr, dpr)

    const cx = size / 2
    const cy = size / 2
    const r = size * 0.38
    const startAngle = Math.PI * 0.75
    const endAngle = Math.PI * 2.25
    const progress = score / 100

    // Background arc
    ctx.beginPath()
    ctx.arc(cx, cy, r, startAngle, endAngle)
    ctx.strokeStyle = '#1f2937'
    ctx.lineWidth = size * 0.1
    ctx.lineCap = 'round'
    ctx.stroke()

    // Color gradient based on score
    const color = score >= 80 ? '#ef4444' : score >= 60 ? '#f97316' : score >= 40 ? '#eab308' : score >= 20 ? '#3b82f6' : '#22c55e'

    // Progress arc
    const progressEnd = startAngle + (endAngle - startAngle) * progress
    ctx.beginPath()
    ctx.arc(cx, cy, r, startAngle, progressEnd)
    ctx.strokeStyle = color
    ctx.lineWidth = size * 0.1
    ctx.lineCap = 'round'
    ctx.stroke()

    // Score text
    ctx.fillStyle = '#ffffff'
    ctx.font = `bold ${size * 0.18}px Inter, system-ui`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(score.toString(), cx, cy - size * 0.04)

    // Label
    ctx.fillStyle = '#6b7280'
    ctx.font = `${size * 0.09}px Inter, system-ui`
    ctx.fillText(label, cx, cy + size * 0.14)
  }, [score, size, label])

  return (
    <canvas
      ref={canvasRef}
      style={{ width: size, height: size }}
      className="select-none"
    />
  )
}
