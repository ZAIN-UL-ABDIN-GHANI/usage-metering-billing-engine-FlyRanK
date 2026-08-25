import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { apiService } from '../services/api'
import { Check } from 'lucide-react'
import { loadStripe } from '@stripe/stripe-js'

interface Plan {
  id: string
  name: string
  price: number
  billing_period: string
  description: string
  features: string[]
  api_calls_limit: number
  ai_tokens_limit: number
}

export default function Plans() {
  const navigate = useNavigate()
  const { tenantId } = useAuthStore()
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)

  const { data: usage } = useQuery({
    queryKey: ['usage'],
    queryFn: () => apiService.getUsage(),
  })

  const plans: Plan[] = [
    {
      id: 'free',
      name: 'Free',
      price: 0,
      billing_period: 'month',
      description: 'Perfect for getting started',
      features: [
        '1,000 API calls/month',
        '100k AI tokens/month',
        'Email support',
        'Basic analytics',
      ],
      api_calls_limit: 1000,
      ai_tokens_limit: 100000,
    },
    {
      id: 'pro',
      name: 'Pro',
      price: 2999,
      billing_period: 'month',
      description: 'For growing businesses',
      features: [
        '100,000 API calls/month',
        '10M AI tokens/month',
        'Priority support',
        'Advanced analytics',
        'Webhook integrations',
        'Custom rate limits',
      ],
      api_calls_limit: 100000,
      ai_tokens_limit: 10000000,
    },
  ]

  const currentPlan = usage?.plan_name.toLowerCase() || 'free'

  const handleUpgrade = async (planId: string) => {
    if (planId === 'free') {
      return
    }

    setSelectedPlan(planId)
    setIsProcessing(true)

    try {
      const response = await apiService.upgradeToProViaCheckout()
      const sessionId = response.session_id

      const stripe = await loadStripe(
        import.meta.env.VITE_STRIPE_PUBLIC_KEY || 'pk_test_demo'
      )
      if (stripe) {
        await stripe.redirectToCheckout({ sessionId })
      }
    } catch (error) {
      console.error('Checkout error:', error)
      setIsProcessing(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Upgrade Your Plan</h1>
        <p className="text-gray-600">
          Choose the plan that fits your needs. Upgrade anytime, downgrade at the end of the month.
        </p>
      </div>

      {/* Plans Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {plans.map((plan) => {
          const isCurrent = plan.id === currentPlan
          const isSelected = selectedPlan === plan.id

          return (
            <div
              key={plan.id}
              className={`rounded-lg border-2 overflow-hidden transition ${
                isCurrent
                  ? 'border-blue-600 bg-blue-50'
                  : isSelected
                    ? 'border-blue-400'
                    : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              {/* Header */}
              <div className={`p-6 ${isCurrent ? 'bg-blue-100' : 'bg-white'}`}>
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-2xl font-bold text-gray-900">{plan.name}</h3>
                    <p className="text-gray-600 text-sm mt-1">{plan.description}</p>
                  </div>
                  {isCurrent && (
                    <span className="bg-blue-600 text-white px-3 py-1 rounded-full text-xs font-semibold">
                      Current Plan
                    </span>
                  )}
                </div>

                {/* Pricing */}
                <div className="mb-6">
                  <div className="text-4xl font-bold text-gray-900">
                    ${(plan.price / 100).toFixed(2)}
                  </div>
                  <p className="text-gray-600 text-sm">
                    per {plan.billing_period}
                  </p>
                </div>

                {/* Limits */}
                <div className="grid grid-cols-2 gap-4 mb-6 p-4 bg-gray-50 rounded">
                  <div>
                    <p className="text-xs font-semibold text-gray-600 uppercase">
                      API Calls
                    </p>
                    <p className="text-lg font-bold text-gray-900">
                      {(plan.api_calls_limit / 1000).toLocaleString()}k
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-gray-600 uppercase">
                      AI Tokens
                    </p>
                    <p className="text-lg font-bold text-gray-900">
                      {plan.ai_tokens_limit >= 1000000
                        ? `${(plan.ai_tokens_limit / 1000000).toLocaleString()}M`
                        : `${(plan.ai_tokens_limit / 1000).toLocaleString()}k`}
                    </p>
                  </div>
                </div>

                {/* CTA Button */}
                {!isCurrent ? (
                  <button
                    onClick={() => handleUpgrade(plan.id)}
                    disabled={isProcessing}
                    className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-2 px-4 rounded-lg transition"
                  >
                    {isProcessing && selectedPlan === plan.id
                      ? 'Processing...'
                      : 'Upgrade Now'}
                  </button>
                ) : (
                  <button
                    disabled
                    className="w-full bg-gray-300 text-gray-600 font-semibold py-2 px-4 rounded-lg cursor-not-allowed"
                  >
                    Current Plan
                  </button>
                )}
              </div>

              {/* Features */}
              <div className="p-6 border-t">
                <h4 className="font-semibold text-gray-900 mb-4">Includes:</h4>
                <ul className="space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-3">
                      <Check className="w-5 h-5 text-green-600 flex-shrink-0" />
                      <span className="text-gray-700 text-sm">{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )
        })}
      </div>

      {/* FAQ */}
      <div className="bg-white rounded-lg shadow p-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Frequently Asked Questions</h2>
        <div className="space-y-6">
          <div>
            <h3 className="font-semibold text-gray-900 mb-2">Can I downgrade my plan?</h3>
            <p className="text-gray-600">
              Yes, you can downgrade to a lower plan at the end of your current billing cycle.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 mb-2">What if I exceed my quota?</h3>
            <p className="text-gray-600">
              Your requests will be rejected with a 429 or 402 status code. Upgrade to a higher plan to continue.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 mb-2">Is there a long-term contract?</h3>
            <p className="text-gray-600">
              No, all plans are month-to-month with no long-term commitment. Cancel anytime.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
