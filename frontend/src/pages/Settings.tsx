import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { AlertCircle } from 'lucide-react'

export default function Settings() {
  const navigate = useNavigate()
  const { email } = useAuthStore()
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [notifications, setNotifications] = useState(true)
  const [emailDigest, setEmailDigest] = useState(true)

  const handleSavePreferences = () => {
    // Simulated save
    setSaveStatus('success')
    setTimeout(() => setSaveStatus('idle'), 3000)
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-600 mt-2">
          Manage your account preferences and notification settings.
        </p>
      </div>

      {/* Account Information */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Account Information</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email Address
            </label>
            <div className="px-4 py-2 bg-gray-50 rounded-lg text-gray-900 font-semibold">
              {email}
            </div>
            <p className="text-xs text-gray-600 mt-2">
              Contact support to change your email address.
            </p>
          </div>
        </div>
      </div>

      {/* API Configuration */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">API Configuration</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              API Key
            </label>
            <div className="flex items-center gap-2">
              <div className="flex-1 px-4 py-2 bg-gray-50 rounded-lg text-gray-900 font-mono text-sm">
                sk_test_••••••••••••••••
              </div>
              <button className="px-4 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition">
                Regenerate
              </button>
            </div>
            <p className="text-xs text-gray-600 mt-2">
              Use this key to authenticate API requests from your application.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Webhook Secret
            </label>
            <div className="flex items-center gap-2">
              <div className="flex-1 px-4 py-2 bg-gray-50 rounded-lg text-gray-900 font-mono text-sm">
                whsec_••••••••••••••••
              </div>
              <button className="px-4 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition">
                Regenerate
              </button>
            </div>
            <p className="text-xs text-gray-600 mt-2">
              Use this secret to verify webhook signatures from Stripe.
            </p>
          </div>
        </div>
      </div>

      {/* Notification Preferences */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Notifications</h2>

        <div className="space-y-4">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={notifications}
              onChange={(e) => setNotifications(e.target.checked)}
              className="w-4 h-4 rounded"
            />
            <div>
              <p className="font-medium text-gray-900">Usage Alerts</p>
              <p className="text-sm text-gray-600">
                Get notified when you reach 80% and 100% of your quota.
              </p>
            </div>
          </label>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={emailDigest}
              onChange={(e) => setEmailDigest(e.target.checked)}
              className="w-4 h-4 rounded"
            />
            <div>
              <p className="font-medium text-gray-900">Weekly Email Digest</p>
              <p className="text-sm text-gray-600">
                Receive a weekly summary of your usage and costs.
              </p>
            </div>
          </label>
        </div>

        {saveStatus === 'success' && (
          <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-green-600" />
            <p className="text-sm text-green-700">Preferences saved successfully!</p>
          </div>
        )}

        <button
          onClick={handleSavePreferences}
          className="mt-4 w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-lg transition"
        >
          Save Preferences
        </button>
      </div>

      {/* Billing Portal */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Billing</h2>

        <div className="space-y-4">
          <p className="text-gray-700">
            Manage your subscription, payment method, and billing history.
          </p>

          <button className="w-full border-2 border-blue-600 text-blue-600 hover:bg-blue-50 font-semibold py-2 px-4 rounded-lg transition">
            Go to Billing Portal
          </button>
        </div>
      </div>

      {/* Support */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Need Help?</h2>

        <p className="text-gray-700 mb-4">
          Have questions or need assistance? We're here to help.
        </p>

        <div className="grid grid-cols-2 gap-4">
          <button className="px-4 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition font-medium">
            Send Email
          </button>
          <button
            onClick={() => navigate('/docs')}
            className="px-4 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition font-medium"
          >
            View Docs
          </button>
        </div>
      </div>
    </div>
  )
}
