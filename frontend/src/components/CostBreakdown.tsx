import React from 'react'
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts'
import { UsageData } from '../services/api'

interface CostBreakdownProps {
  usage: UsageData
}

export default function CostBreakdown({ usage }: CostBreakdownProps) {
  // Calculate costs
  const apiCallCost = (usage.api_calls_used / 1000) * 0.01 * 100 // $0.01 per 1k calls
  const tokenCost = (usage.ai_tokens_used / 1000) * 0.005 * 100 // $0.005 per 1k tokens
  const totalCost = usage.current_cost

  const data = [
    { name: 'API Calls', value: apiCallCost, label: `$${(apiCallCost / 100).toFixed(2)}` },
    { name: 'AI Tokens', value: tokenCost, label: `$${(tokenCost / 100).toFixed(2)}` },
  ].filter((item) => item.value > 0)

  const COLORS = ['#3b82f6', '#a855f7']

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Cost Breakdown</h2>
      
      {data.length > 0 ? (
        <div className="flex flex-col md:flex-row items-center gap-8">
          <div className="w-full md:w-1/2">
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={data}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, value }) => `${name}: $${(value / 100).toFixed(2)}`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {data.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value) => `$${(value as number / 100).toFixed(2)}`}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="w-full md:w-1/2 space-y-4">
            {data.map((item, index) => (
              <div key={item.name} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: COLORS[index % COLORS.length] }}
                  ></div>
                  <span className="text-gray-700">{item.name}</span>
                </div>
                <span className="font-semibold text-gray-900">${(item.value / 100).toFixed(2)}</span>
              </div>
            ))}

            <div className="border-t pt-4 mt-4">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-gray-900">Total This Month</span>
                <span className="text-xl font-bold text-blue-600">
                  ${(totalCost / 100).toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <p className="text-gray-600">No usage data available for this period.</p>
      )}
    </div>
  )
}
