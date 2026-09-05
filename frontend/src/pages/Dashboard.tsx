import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, TrendingUp, Zap } from 'lucide-react'
import { apiService, UsageData } from '../services/api'
import UsageBar from '../components/UsageBar'
import CostBreakdown from '../components/CostBreakdown'

const DEFAULT_USAGE: UsageData = {
  api_calls_used: 0,
  api_calls_limit: 0,
  ai_tokens_used: 0,
  ai_tokens_limit: 0,
  current_cost: 0,
  billing_period_start: '',
  billing_period_end: '',
  plan_name: 'Unknown',
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { data: usage, isLoading, error } = useQuery({
    queryKey: ['usage'],
    queryFn: () => apiService.getUsage(),
    refetchInterval: 30000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-gray-600">Loading usage data...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
        <AlertCircle className="w-5 h-5 text-red-600" />
        <div>
          <p className="font-semibold text-red-900">Error loading usage data</p>
          <p className="text-sm text-red-700">Please refresh the page to try again.</p>
        </div>
      </div>
    )
  }

  const usageData = usage ?? DEFAULT_USAGE
  const apiCallsUsed = usageData?.api_calls_used ?? 0
  const apiCallsLimit = usageData?.api_calls_limit ?? 0
  const aiTokensUsed = usageData?.ai_tokens_used ?? 0
  const aiTokensLimit = usageData?.ai_tokens_limit ?? 0
  const currentCost = usageData?.current_cost ?? 0

  const apiCallsPercentage =
    apiCallsLimit > 0 ? (apiCallsUsed / apiCallsLimit) * 100 : 0
  const tokensPercentage =
    aiTokensLimit > 0 ? (aiTokensUsed / aiTokensLimit) * 100 : 0

  const isNearLimit = apiCallsPercentage > 80 || tokensPercentage > 80

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg p-8">
        <h1 className="text-3xl font-bold mb-2">
          Welcome back
        </h1>
        <p className="text-blue-100">
          Current plan: <span className="font-semibold">{usageData.plan_name || 'Unknown'}</span>
        </p>
      </div>

      {/* Alert if near limit */}
      {isNearLimit && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-yellow-600" />
          <div>
            <p className="font-semibold text-yellow-900">Usage approaching limit</p>
            <p className="text-sm text-yellow-700">
              You're using more than 80% of your quota. Consider upgrading to avoid service interruption.
            </p>
            <button
              onClick={() => navigate('/plans')}
              className="text-sm font-semibold text-yellow-700 hover:text-yellow-800 mt-2"
            >
              View plans →
            </button>
          </div>
        </div>
      )}

      {/* Usage Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* API Calls */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">API Calls</h3>
            <Zap className="w-5 h-5 text-blue-600" />
          </div>
          <div className="text-2xl font-bold text-gray-900 mb-2">
            {(apiCallsUsed ?? 0).toLocaleString()}
            <span className="text-lg text-gray-600 ml-2">
              / {(apiCallsLimit ?? 0).toLocaleString()}
            </span>
          </div>
          <UsageBar percentage={apiCallsPercentage} />
          <p className="text-xs text-gray-600 mt-2">
            {Math.max(0, Math.round(apiCallsLimit - apiCallsUsed)).toLocaleString()} calls remaining this month
          </p>
        </div>

        {/* AI Tokens */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">AI Tokens</h3>
            <TrendingUp className="w-5 h-5 text-purple-600" />
          </div>
          <div className="text-2xl font-bold text-gray-900 mb-2">
            {(aiTokensUsed ?? 0).toLocaleString()}
            <span className="text-lg text-gray-600 ml-2">
              / {(aiTokensLimit ?? 0).toLocaleString()}
            </span>
          </div>
          <UsageBar percentage={tokensPercentage} />
          <p className="text-xs text-gray-600 mt-2">
            {Math.max(0, Math.round(aiTokensLimit - aiTokensUsed)).toLocaleString()} tokens remaining this month
          </p>
        </div>
      </div>

      {/* Cost & Period Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-600 mb-2">Current Month Cost</h3>
          <div className="text-3xl font-bold text-gray-900">
            ${((currentCost ?? 0) / 100).toFixed(2)}
          </div>
          <p className="text-xs text-gray-600 mt-2">Based on current usage</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-600 mb-2">Billing Period</h3>
          <div className="text-sm font-semibold text-gray-900">
            {usageData.billing_period_start
              ? new Date(usageData.billing_period_start).toLocaleDateString()
              : '—'}
            <br />
            {usageData.billing_period_end
              ? new Date(usageData.billing_period_end).toLocaleDateString()
              : '—'}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-600 mb-2">Quick Actions</h3>
          <div className="space-y-2">
            <button
              onClick={() => navigate('/usage')}
              className="w-full px-3 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded transition"
            >
              View Details
            </button>
            {usageData.plan_name === 'Free' && (
              <button
                onClick={() => navigate('/plans')}
                className="w-full px-3 py-2 text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 rounded transition"
              >
                Upgrade
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Cost Breakdown */}
      <CostBreakdown usage={usageData} />
    </div>
  )
}
