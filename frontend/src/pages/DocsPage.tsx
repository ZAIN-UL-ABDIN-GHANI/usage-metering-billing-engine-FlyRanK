import { ArrowLeft, BarChart3, CreditCard, HelpCircle, Gauge, Layers } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const sections = [
  {
    title: 'What is FlyRank?',
    icon: Gauge,
    text: 'FlyRank is an automatic counting and billing service for digital software. Think of it like an electricity meter, but for online applications: it counts what you use and helps calculate your monthly bill.',
  },
  {
    title: 'How Usage Metering Works',
    icon: BarChart3,
    text: 'Whenever your application performs an activity, such as making a call, searching data, or generating a report, FlyRank adds it to your usage count. The Dashboard shows this month\'s usage, while Usage shows more detail. Alerts can warn you at 80% and 100% of your limit.',
  },
  {
    title: 'Understanding Subscription Plans',
    icon: Layers,
    text: 'Basic plans are suited to small users and include a fixed monthly quota. Pro plans offer higher limits and priority support for growing businesses. Enterprise plans can include custom limits and dedicated assistance for larger companies.',
  },
  {
    title: 'How Billing & Payments Work',
    icon: CreditCard,
    text: 'At the end of each monthly cycle, FlyRank calculates your charges from your plan and usage. Payments are handled securely through Stripe. You can manage your payment method and billing history from the Billing Portal in Settings.',
  },
]

export default function DocsPage() {
  const navigate = useNavigate()

  return (
    <div className="max-w-4xl space-y-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-blue-600 uppercase tracking-wide">
            FlyRank Help
          </p>
          <h1 className="text-3xl font-bold text-gray-900 mt-2">Welcome to the FlyRank User Guide</h1>
          <p className="text-gray-600 mt-3 max-w-2xl">
            A simple guide to understanding your usage, plans, billing, and support options.
          </p>
        </div>
        <button
          type="button"
          onClick={() => navigate('/settings')}
          className="inline-flex items-center gap-2 border border-gray-300 hover:bg-gray-50 text-gray-700 font-semibold py-2 px-4 rounded-lg transition whitespace-nowrap"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Settings
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {sections.map(({ title, icon: Icon, text }) => (
          <section key={title} className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="bg-blue-50 text-blue-600 rounded-lg p-2">
                <Icon className="w-5 h-5" />
              </div>
              <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
            </div>
            <p className="text-gray-600 leading-7">{text}</p>
          </section>
        ))}
      </div>

      <section className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="bg-blue-50 text-blue-600 rounded-lg p-2">
            <HelpCircle className="w-5 h-5" />
          </div>
          <h2 className="text-lg font-semibold text-gray-900">Common Questions & Support</h2>
        </div>

        <div className="divide-y divide-gray-200">
          <details className="py-4" open>
            <summary className="cursor-pointer font-semibold text-gray-900">
              What happens if I reach 100% of my monthly limit?
            </summary>
            <p className="text-gray-600 leading-7 mt-3">
              Depending on your setup, you can upgrade your plan under Plans or pay for additional usage.
            </p>
          </details>
          <details className="py-4">
            <summary className="cursor-pointer font-semibold text-gray-900">
              How do I change my credit card?
            </summary>
            <p className="text-gray-600 leading-7 mt-3">
              Open Settings and choose Go to Billing Portal. You can safely add or remove payment cards there.
            </p>
          </details>
          <details className="py-4">
            <summary className="cursor-pointer font-semibold text-gray-900">
              How do I get human help?
            </summary>
            <p className="text-gray-600 leading-7 mt-3">
              Open Settings and choose Send Email in the Need Help? section to contact support.
            </p>
          </details>
        </div>
      </section>
    </div>
  )
}