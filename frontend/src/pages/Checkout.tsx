import React, { useEffect, useState } from 'react'
import { useStripe, useElements, PaymentElement } from '@stripe/react-stripe-js'
import { useSearchParams, useNavigate } from 'react-router-dom'

export default function Checkout() {
  const stripe = useStripe()
  const elements = useElements()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const clientSecret = searchParams.get('client_secret')

  useEffect(() => {
    if (!clientSecret) {
      navigate('/plans')
    }
  }, [clientSecret, navigate])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!stripe || !elements) {
      return
    }

    setIsProcessing(true)
    setError(null)

    try {
      const result = await stripe.confirmPayment({
        elements,
        redirect: 'if_required',
      })

      if (result.error) {
        setError(result.error.message || 'An error occurred during payment')
        setIsProcessing(false)
      } else {
        navigate('/upgrade-success')
      }
    } catch (err: any) {
      setError('An error occurred during payment processing')
      setIsProcessing(false)
    }
  }

  if (!clientSecret) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-gray-600">Redirecting to plans...</div>
      </div>
    )
  }

  return (
    <div className="max-w-md mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Complete Your Upgrade</h1>
        <p className="text-gray-600 mt-2">
          You're upgrading to Pro. Enter your payment details below.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-6">
        <PaymentElement />

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <button
          type="submit"
          disabled={!stripe || isProcessing}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-3 px-4 rounded-lg transition"
        >
          {isProcessing ? 'Processing...' : 'Pay Now'}
        </button>
      </form>

      <p className="text-xs text-gray-600 text-center">
        Your payment information is securely processed by Stripe.
      </p>
    </div>
  )
}
