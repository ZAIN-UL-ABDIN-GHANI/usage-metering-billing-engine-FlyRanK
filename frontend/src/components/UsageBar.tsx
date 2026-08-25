import React from 'react'

interface UsageBarProps {
  percentage: number
  showLabel?: boolean
}

export default function UsageBar({ percentage, showLabel = true }: UsageBarProps) {
  const color =
    percentage > 90 ? 'bg-red-500' : percentage > 70 ? 'bg-yellow-500' : 'bg-green-500'

  return (
    <div>
      <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
        <div
          className={`h-full transition-all ${color}`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        ></div>
      </div>
      {showLabel && (
        <p className="text-xs text-gray-600 mt-1">
          {percentage.toFixed(1)}% used
        </p>
      )}
    </div>
  )
}
