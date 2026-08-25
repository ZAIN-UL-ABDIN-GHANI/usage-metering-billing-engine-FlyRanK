import React, { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle } from 'lucide-react'

export default function UpgradeSuccess() {
  const navigate = useNavigate()

  useEffect(() => {
    const timer = setTimeout(() => {
      navigate('/')
    }, 3000)

    return () => clearTimeout(timer)
  }, [navigate])

  return (
    <div className="flex items-center justify-center h-screen bg-gray-50">
      <div className="text-center space-y-6">
        <div className="flex justify-center">
          <CheckCircle className="w-16 h-16 text-green-600" />
        </div>

        <div>
          <h1 className="text-3xl font-bold text-gray-900">Upgrade Successful!</h1>
          <p className="text-gray-600 mt-2">
            Welcome to Pro. Your plan is now active and your higher limits are in effect.
          </p>
        </div>

        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-sm text-green-700">
            You now have access to 100,000 API calls and 10M AI tokens per month.
          </p>
        </div>

        <p className="text-sm text-gray-600">
          Redirecting to dashboard in 3 seconds...
        </p>

        <button
          onClick={() => navigate('/')}
          className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-6 rounded-lg transition"
        >
          Go to Dashboard Now
        </button>
      </div>
    </div>
  )
}
