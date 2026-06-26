import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Play, Pause, SkipForward, X, ChevronRight, Clock, FileCode, TestTube, Star } from 'lucide-react'
import { PIPELINE_NODES } from '@/lib/mockData'
import { cn } from '@/lib/utils'
import type { PipelineNode } from '@/types'

const EDGE_PAIRS: [string, string][] = [
  ['transaction', 'feature_store'],
  ['feature_store', 'fast_screening'],
  ['transaction', 'fast_screening'],
  ['fast_screening', 'behavior_agent'],
  ['fast_screening', 'device_agent'],
  ['fast_screening', 'geo_agent'],
  ['fast_screening', 'merchant_agent'],
  ['fast_screening', 'graph_agent'],
  ['behavior_agent', 'consensus'],
  ['device_agent', 'consensus'],
  ['geo_agent', 'consensus'],
  ['merchant_agent', 'consensus'],
  ['graph_agent', 'consensus'],
  ['consensus', 'investigation'],
  ['investigation', 'counterfactual'],
  ['investigation', 'explainability'],
  ['investigation', 'storytelling'],
  ['investigation', 'feedback_store'],
  ['feedback_store', 'pattern_evolution'],
  ['pattern_evolution', 'reputation_updater'],
  ['reputation_updater', 'future_detection'],
  ['future_detection', 'fast_screening'],
]

const DEMO_STEPS: Array<{ nodeId: string; message: string; latency: string }> = [
  { nodeId: 'transaction', message: 'Transaction received: $4,299 at Electronics Plus · POST /detect', latency: '0ms' },
  { nodeId: 'feature_store', message: 'Feature cache hit: velocity=3 txns/8min, risk_elevation=8.1, device_age=24h', latency: '5ms' },
  { nodeId: 'fast_screening', message: 'Pre-screen score: 72.4 + elevation boost +8.1 = 80.5 → ROUTE TO AGENTS', latency: '19ms' },
  { nodeId: 'behavior_agent', message: 'Behavioral deviation: amount 2.1× baseline, new merchant category → score 78', latency: '95ms' },
  { nodeId: 'device_agent', message: 'Device fingerprint new (24h) + VPN + 0 prior txns on device → score 84', latency: '87ms' },
  { nodeId: 'geo_agent', message: 'Unusual location: no prior history in this city, cross-border flag → score 71', latency: '102ms' },
  { nodeId: 'merchant_agent', message: 'Merchant rep 0.68, high-risk electronics category → score 63', latency: '108ms' },
  { nodeId: 'graph_agent', message: 'FraudRing: 2 hops to confirmed fraudster cluster (ring_id: fr_9821) → score 91', latency: '142ms' },
  { nodeId: 'consensus', message: 'Weighted consensus: 80.2 (5/5 agents above threshold, agreement penalty 0) → HIGH RISK', latency: '242ms' },
  { nodeId: 'investigation', message: 'Deep LLM investigation: kill chain = MONETIZATION, sequence = card-testing ring', latency: '680ms' },
  { nodeId: 'counterfactual', message: 'If amount < $500 AND known device: would approve. Minimum change to avoid block.', latency: '720ms' },
  { nodeId: 'explainability', message: 'Decision: BLOCK (confidence 0.94). Graph risk + device novelty + behavioral spike.', latency: '780ms' },
  { nodeId: 'storytelling', message: 'Narrative: New device from fraud-linked cluster, 2.1× amount spike in high-risk category.', latency: '820ms' },
  { nodeId: 'feedback_store', message: 'Decision persisted. Awaiting analyst feedback to close the learning loop.', latency: '825ms' },
  { nodeId: 'pattern_evolution', message: 'Pattern evolution: 3 FNs on card_testing → threshold 0.65→0.61, signal boost ×1.3', latency: '830ms' },
  { nodeId: 'reputation_updater', message: 'Device reputation penalized −0.15. Merchant flagged. risk_elevation +12 in Redis.', latency: '835ms' },
  { nodeId: 'future_detection', message: 'Loop closed: next transaction from this device cluster will score +12 points higher.', latency: '840ms' },
]

const NODE_TYPE_COLOR: Record<string, string> = {
  input: 'border-blue-500/60 bg-blue-500/10',
  service: 'border-cyan-500/60 bg-cyan-500/10',
  agent: 'border-purple-500/60 bg-purple-500/10',
  consensus: 'border-yellow-500/60 bg-yellow-500/10',
  output: 'border-green-500/60 bg-green-500/10',
  feedback: 'border-pink-500/60 bg-pink-500/10',
}

const NODE_TYPE_DOT: Record<string, string> = {
  input: 'bg-blue-400',
  service: 'bg-cyan-400',
  agent: 'bg-purple-400',
  consensus: 'bg-yellow-400',
  output: 'bg-green-400',
  feedback: 'bg-pink-400',
}

interface EdgeProps {
  from: PipelineNode
  to: PipelineNode
  active: boolean
  scale: number
}

function Edge({ from, to, active, scale }: EdgeProps) {
  const x1 = (from.x + 60) * scale
  const y1 = (from.y + 20) * scale
  const x2 = to.x * scale
  const y2 = (to.y + 20) * scale
  const mx = (x1 + x2) / 2

  return (
    <g>
      <path
        d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`}
        fill="none"
        stroke={active ? '#60a5fa' : '#1f2937'}
        strokeWidth={active ? 2 : 1.5}
        opacity={active ? 1 : 0.5}
        className="transition-all duration-500"
      />
      {active && (
        <motion.circle
          r={4}
          fill="#60a5fa"
          filter="url(#glow)"
          initial={{ offsetDistance: '0%' }}
          animate={{ offsetDistance: '100%' }}
          transition={{ duration: 0.8, ease: 'easeInOut' }}
          style={{
            offsetPath: `path("M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}")`,
          } as React.CSSProperties}
        />
      )}
    </g>
  )
}

export function Pipeline() {
  const [selectedNode, setSelectedNode] = useState<PipelineNode | null>(null)
  const [activeStep, setActiveStep] = useState<number>(-1)
  const [playing, setPlaying] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)

  useEffect(() => {
    const update = () => {
      if (!containerRef.current) return
      const w = containerRef.current.clientWidth
      setScale(Math.min(1, w / 900))
    }
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  useEffect(() => {
    if (!playing) { if (intervalRef.current) clearInterval(intervalRef.current); return }
    intervalRef.current = setInterval(() => {
      setActiveStep(prev => {
        if (prev >= DEMO_STEPS.length - 1) { setPlaying(false); return prev }
        return prev + 1
      })
    }, 900)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [playing])

  const activeNodeId = activeStep >= 0 ? DEMO_STEPS[activeStep].nodeId : null
  const activeEdges = new Set<string>()
  if (activeStep >= 1) {
    for (let i = 0; i <= activeStep; i++) {
      const step = DEMO_STEPS[i]
      const prev = i > 0 ? DEMO_STEPS[i - 1] : null
      if (prev) activeEdges.add(`${prev.nodeId}-${step.nodeId}`)
    }
  }

  const handlePlay = () => {
    if (activeStep >= DEMO_STEPS.length - 1) setActiveStep(-1)
    setPlaying(true)
  }

  const handleStep = () => {
    setPlaying(false)
    setActiveStep(prev => Math.min(prev + 1, DEMO_STEPS.length - 1))
  }

  const canvasWidth = 900
  const canvasHeight = 520

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-white">AI Pipeline Visualization</h1>
          <p className="text-xs text-gray-500 mt-0.5">Interactive map of the fraud detection data flow</p>
        </div>

        {/* Demo controls */}
        <div className="flex items-center gap-2">
          <div className="text-xs text-gray-500">
            {activeStep >= 0 ? `Step ${activeStep + 1}/${DEMO_STEPS.length}` : 'Click a node or press Play'}
          </div>
          <button
            onClick={() => { setActiveStep(-1); setPlaying(false) }}
            className="text-xs px-2 py-1.5 rounded-lg border border-gray-700 text-gray-400 hover:text-white hover:border-gray-600 transition-colors"
          >
            Reset
          </button>
          <button
            onClick={handleStep}
            disabled={activeStep >= DEMO_STEPS.length - 1}
            className="text-xs px-2 py-1.5 rounded-lg border border-gray-700 text-gray-400 hover:text-white hover:border-gray-600 transition-colors disabled:opacity-40"
          >
            <SkipForward className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={playing ? () => setPlaying(false) : handlePlay}
            className={cn(
              'flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium transition-colors',
              playing
                ? 'bg-yellow-500/20 border border-yellow-500/40 text-yellow-400 hover:bg-yellow-500/30'
                : 'bg-blue-500/20 border border-blue-500/40 text-blue-400 hover:bg-blue-500/30'
            )}
          >
            {playing ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            {playing ? 'Pause' : 'Live Demo'}
          </button>
        </div>
      </div>

      {/* Step message bar */}
      <AnimatePresence>
        {activeStep >= 0 && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="bg-blue-500/10 border border-blue-500/30 rounded-xl px-4 py-2.5 flex items-center gap-3"
          >
            <div className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-500/20 border border-blue-500/40 flex items-center justify-center text-[10px] text-blue-400 font-bold">
              {activeStep + 1}
            </div>
            <div className="flex-1 text-sm text-blue-200">{DEMO_STEPS[activeStep].message}</div>
            <div className="text-xs font-mono text-blue-400/70 flex-shrink-0">
              T+{DEMO_STEPS[activeStep].latency}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Canvas + detail panel */}
      <div className="flex gap-4">
        {/* SVG Canvas */}
        <div
          ref={containerRef}
          className="flex-1 bg-gray-900 border border-gray-800 rounded-xl overflow-hidden"
          style={{ minHeight: canvasHeight * scale + 32 }}
        >
          <svg
            width={canvasWidth * scale}
            height={canvasHeight * scale}
            viewBox={`0 0 ${canvasWidth * scale} ${canvasHeight * scale}`}
            className="block"
          >
            <defs>
              <filter id="glow">
                <feGaussianBlur stdDeviation="3" result="coloredBlur" />
                <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
              <filter id="nodeGlow">
                <feGaussianBlur stdDeviation="6" result="coloredBlur" />
                <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            </defs>

            {/* Edges */}
            {EDGE_PAIRS.map(([fromId, toId]) => {
              const from = PIPELINE_NODES.find(n => n.id === fromId)
              const to = PIPELINE_NODES.find(n => n.id === toId)
              if (!from || !to) return null
              return (
                <Edge
                  key={`${fromId}-${toId}`}
                  from={from}
                  to={to}
                  active={activeEdges.has(`${fromId}-${toId}`)}
                  scale={scale}
                />
              )
            })}

            {/* Nodes */}
            {PIPELINE_NODES.map(node => {
              const isActive = activeNodeId === node.id
              const isSelected = selectedNode?.id === node.id
              const wasVisited = DEMO_STEPS.slice(0, activeStep + 1).some(s => s.nodeId === node.id)

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x * scale}, ${node.y * scale})`}
                  onClick={() => setSelectedNode(isSelected ? null : node)}
                  className="cursor-pointer"
                >
                  {/* Glow ring when active */}
                  {isActive && (
                    <motion.rect
                      x={-4} y={-4}
                      width={124} height={48}
                      rx={10}
                      fill="none"
                      stroke="#60a5fa"
                      strokeWidth={2}
                      opacity={0.6}
                      animate={{ opacity: [0.3, 0.8, 0.3] }}
                      transition={{ repeat: Infinity, duration: 1.2 }}
                      filter="url(#nodeGlow)"
                    />
                  )}

                  {/* Node box */}
                  <rect
                    x={0} y={0}
                    width={116} height={40}
                    rx={8}
                    fill={isActive ? '#1e3a5f' : isSelected ? '#1a2744' : wasVisited ? '#151f2e' : '#111827'}
                    stroke={isActive ? '#3b82f6' : isSelected ? '#6366f1' : wasVisited ? '#374151' : '#1f2937'}
                    strokeWidth={isActive || isSelected ? 1.5 : 1}
                    className="transition-all duration-300"
                  />

                  {/* Type dot */}
                  <circle
                    cx={10} cy={20}
                    r={4}
                    fill={NODE_TYPE_DOT[node.type] ?? '#6b7280'}
                    opacity={wasVisited || isActive ? 1 : 0.4}
                  />

                  {/* Label */}
                  <text
                    x={22} y={15}
                    fill={isActive ? '#e0f2fe' : wasVisited ? '#d1d5db' : '#6b7280'}
                    fontSize={9 * Math.min(1, scale + 0.2)}
                    fontWeight={isActive ? 700 : 500}
                    fontFamily="Inter, system-ui, sans-serif"
                    className="transition-all duration-300 select-none"
                  >
                    {node.label}
                  </text>

                  {/* Latency */}
                  <text
                    x={22} y={28}
                    fill={isActive ? '#93c5fd' : '#374151'}
                    fontSize={8 * Math.min(1, scale + 0.2)}
                    fontFamily="Inter, system-ui, monospace"
                    className="select-none"
                  >
                    {node.latency}
                  </text>

                  {/* Active pulse dot */}
                  {isActive && (
                    <motion.circle
                      cx={108} cy={8} r={4}
                      fill="#22c55e"
                      animate={{ r: [3, 5, 3], opacity: [0.6, 1, 0.6] }}
                      transition={{ repeat: Infinity, duration: 0.8 }}
                    />
                  )}
                </g>
              )
            })}
          </svg>
        </div>

        {/* Node detail panel */}
        <AnimatePresence>
          {selectedNode && (
            <motion.div
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 24 }}
              transition={{ type: 'spring', damping: 24, stiffness: 280 }}
              className="w-72 bg-gray-900 border border-gray-800 rounded-xl p-4 flex-shrink-0 overflow-y-auto"
              style={{ maxHeight: canvasHeight * scale + 32 }}
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className={cn(
                    'inline-flex items-center gap-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-full border mb-1.5',
                    NODE_TYPE_COLOR[selectedNode.type] ?? 'border-gray-700 bg-gray-800'
                  )}>
                    <div className={cn('w-1.5 h-1.5 rounded-full', NODE_TYPE_DOT[selectedNode.type] ?? 'bg-gray-400')} />
                    {selectedNode.type.replace(/_/g, ' ').toUpperCase()}
                  </div>
                  <h3 className="text-sm font-bold text-white">{selectedNode.label}</h3>
                  <div className="text-[10px] font-mono text-gray-500 mt-0.5">{selectedNode.latency}</div>
                </div>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="p-1 text-gray-600 hover:text-white transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Purpose */}
              <p className="text-xs text-gray-400 leading-relaxed mb-3">{selectedNode.purpose ?? selectedNode.description}</p>

              {/* Stats row */}
              <div className="grid grid-cols-3 gap-2 mb-3">
                {selectedNode.auditScore !== undefined && (
                  <div className="bg-gray-800/60 rounded-lg p-2 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <Star className="w-3 h-3 text-yellow-400" />
                      <span className="text-sm font-bold text-white">{selectedNode.auditScore}</span>
                    </div>
                    <div className="text-[10px] text-gray-500">Audit</div>
                  </div>
                )}
                {selectedNode.testCount !== undefined && (
                  <div className="bg-gray-800/60 rounded-lg p-2 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <TestTube className="w-3 h-3 text-green-400" />
                      <span className="text-sm font-bold text-white">{selectedNode.testCount}</span>
                    </div>
                    <div className="text-[10px] text-gray-500">Tests</div>
                  </div>
                )}
                {selectedNode.files && (
                  <div className="bg-gray-800/60 rounded-lg p-2 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <FileCode className="w-3 h-3 text-blue-400" />
                      <span className="text-sm font-bold text-white">{selectedNode.files.length}</span>
                    </div>
                    <div className="text-[10px] text-gray-500">Files</div>
                  </div>
                )}
              </div>

              {/* Inputs */}
              {selectedNode.inputs && selectedNode.inputs.length > 0 && (
                <InfoBlock title="Inputs" items={selectedNode.inputs} color="text-blue-400" />
              )}

              {/* Outputs */}
              {selectedNode.outputs && selectedNode.outputs.length > 0 && (
                <InfoBlock title="Outputs" items={selectedNode.outputs} color="text-green-400" />
              )}

              {/* Files */}
              {selectedNode.files && selectedNode.files.length > 0 && (
                <div className="mb-3">
                  <div className="text-[10px] uppercase tracking-wide text-gray-500 mb-1.5">Source Files</div>
                  <div className="space-y-1">
                    {selectedNode.files.map(f => (
                      <div key={f} className="text-[10px] font-mono text-gray-400 bg-gray-800/40 px-2 py-1 rounded">
                        {f}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Latency breakdown */}
              <div className="bg-gray-800/40 rounded-lg px-3 py-2 flex items-center gap-2">
                <Clock className="w-3.5 h-3.5 text-gray-400" />
                <span className="text-xs text-gray-300">Typical latency:</span>
                <span className="text-xs font-mono text-white ml-auto">{selectedNode.latency}</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500">
        {Object.entries(NODE_TYPE_DOT).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1.5">
            <div className={cn('w-2 h-2 rounded-full', color)} />
            <span className="capitalize">{type}</span>
          </div>
        ))}
        <div className="flex items-center gap-1.5 ml-4">
          <div className="w-6 h-px bg-blue-400" />
          <span>Active data flow</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-6 h-px bg-gray-700" />
          <span>Inactive edge</span>
        </div>
      </div>
    </div>
  )
}

function InfoBlock({ title, items, color }: { title: string; items: string[]; color: string }) {
  return (
    <div className="mb-3">
      <div className="text-[10px] uppercase tracking-wide text-gray-500 mb-1.5">{title}</div>
      <div className="space-y-1">
        {items.map(item => (
          <div key={item} className="flex items-center gap-1.5 text-[10px]">
            <ChevronRight className={cn('w-3 h-3 flex-shrink-0', color)} />
            <span className="text-gray-400">{item}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
