import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiService, UsageData } from '../services/api'
import UsageBar from '../components/UsageBar'
import { AlertCircle } from 'lucide-react'

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

export default function UsageDetail() {
  const { data: usage, isLoading, error } = useQuery({
    queryKey: ['usage'],
    queryFn: () => apiService.getUsage(),
    refetchInterval: 30000,
  })

  if (isLoading) {
    return <div className="text-center py-8 text-gray-600">Loading...</div>
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
        <AlertCircle className="w-5 h-5 text-red-600" />
        <p className="text-sm text-red-700">Unable to load usage data.</p>
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Usage Details</h1>
        <p className="text-gray-600 mt-2">
          Comprehensive view of your usage metrics for the current billing period.
        </p>
      </div>

      {/* API Calls Detailed */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">API Calls</h2>

        <div className="mb-6">
          <div className="flex justify-between items-center mb-2">
            <span className="text-gray-700">Usage</span>
            <span className="text-2xl font-bold text-gray-900">
              {(apiCallsUsed ?? 0).toLocaleString()}/
              {(apiCallsLimit ?? 0).toLocaleString()}
            </span>
          </div>
          <UsageBar percentage={apiCallsPercentage} />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="bg-blue-50 rounded p-4">
            <p className="text-xs font-semibold text-gray-600 uppercase">Used</p>
            <p className="text-2xl font-bold text-blue-600">
              {(apiCallsUsed ?? 0).toLocaleString()}
            </p>
          </div>
          <div className="bg-gray-50 rounded p-4">
            <p className="text-xs font-semibold text-gray-600 uppercase">Remaining</p>
            <p className="text-2xl font-bold text-gray-900">
              {Math.max(0, apiCallsLimit - apiCallsUsed).toLocaleString()}
            </p>
          </div>
          <div className="bg-purple-50 rounded p-4">
            <p className="text-xs font-semibold text-gray-600 uppercase">Percent</p>
            <p className="text-2xl font-bold text-purple-600">
              {apiCallsPercentage.toFixed(1)}%
            </p>
          </div>
        </div>
      </div>

      {/* AI Tokens Detailed */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">AI Tokens</h2>

        <div className="mb-6">
          <div className="flex justify-between items-center mb-2">
            <span className="text-gray-700">Usage</span>
            <span className="text-2xl font-bold text-gray-900">
              {(aiTokensUsed ?? 0).toLocaleString()}/
              {(aiTokensLimit ?? 0).toLocaleString()}
            </span>
          </div>
          <UsageBar percentage={tokensPercentage} />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="bg-blue-50 rounded p-4">
            <p className="text-xs font-semibold text-gray-600 uppercase">Used</p>
            <p className="text-2xl font-bold text-blue-600">
              {((aiTokensUsed ?? 0) / 1000).toLocaleString()}k
            </p>
          </div>
          <div className="bg-gray-50 rounded p-4">
            <p className="text-xs font-semibold text-gray-600 uppercase">Remaining</p>
            <p className="text-2xl font-bold text-gray-900">
              {((Math.max(0, aiTokensLimit - aiTokensUsed) / 1000) ?? 0).toLocaleString()}k
            </p>
          </div>
          <div className="bg-purple-50 rounded p-4">
            <p className="text-xs font-semibold text-gray-600 uppercase">Percent</p>
            <p className="text-2xl font-bold text-purple-600">
              {tokensPercentage.toFixed(1)}%
            </p>
          </div>
        </div>
      </div>

      {/* Billing Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Billing Period</h3>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-600">Start Date</span>
              <span className="font-semibold text-gray-900">
                {usageData.billing_period_start
                  ? new Date(usageData.billing_period_start).toLocaleDateString()
                  : '—'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">End Date</span>
              <span className="font-semibold text-gray-900">
                {usageData.billing_period_end
                  ? new Date(usageData.billing_period_end).toLocaleDateString()
                  : '—'}
              </span>
            </div>
            <div className="flex justify-between pt-3 border-t">
              <span className="text-gray-600">Days Remaining</span>
              <span className="font-semibold text-gray-900">
                {usageData.billing_period_end
                  ? Math.max(
                      0,
                      Math.ceil(
                        (new Date(usageData.billing_period_end).getTime() -
                          new Date().getTime()) /
                          (1000 * 60 * 60 * 24)
                      )
                    )
                  : 0}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Current Cost</h3>
          <div className="space-y-3">
            <div className="text-4xl font-bold text-blue-600 mb-4">
              ${((currentCost ?? 0) / 100).toFixed(2)}
            </div>
            <p className="text-sm text-gray-600">
              Based on current usage this billing period.
            </p>
            <div className="bg-blue-50 rounded p-3 mt-4">
              <p className="text-xs text-blue-700">
                💡 Tip: You can downgrade your plan at the end of the billing cycle to reduce costs.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
