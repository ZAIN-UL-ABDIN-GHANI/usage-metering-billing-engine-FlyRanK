import React, { ReactNode } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { LogOut, Settings, BarChart3, Zap, Home } from 'lucide-react'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { logout, email } = useAuthStore()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    { path: '/', label: 'Dashboard', icon: Home },
    { path: '/usage', label: 'Usage', icon: BarChart3 },
    { path: '/plans', label: 'Plans', icon: Zap },
  ]

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="w-64 bg-white shadow-lg">
        <div className="p-6 border-b">
          <h1 className="text-2xl font-bold text-blue-600">FlyRank</h1>
          <p className="text-xs text-gray-600 mt-1">Billing Dashboard</p>
        </div>

        <nav className="p-4 space-y-2">
          {navItems.map(({ path, label, icon: Icon }) => (
            <Link
              key={path}
              to={path}
              className={`flex items-center gap-3 px-4 py-2 rounded-lg transition ${
                location.pathname === path
                  ? 'bg-blue-50 text-blue-600 font-semibold'
                  : 'text-gray-700 hover:bg-gray-50'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </Link>
          ))}
        </nav>

        {/* Divider */}
        <div className="border-t my-4"></div>

        {/* Settings & Logout */}
        <div className="p-4 space-y-2">
          <Link
            to="/settings"
            className={`flex items-center gap-3 px-4 py-2 rounded-lg transition ${
              location.pathname === '/settings'
                ? 'bg-blue-50 text-blue-600 font-semibold'
                : 'text-gray-700 hover:bg-gray-50'
            }`}
          >
            <Settings className="w-4 h-4" />
            Settings
          </Link>

          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-2 text-gray-700 hover:bg-gray-50 rounded-lg transition text-left"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>

        {/* User Info */}
        <div className="absolute bottom-0 w-64 p-4 border-t bg-gray-50">
          <p className="text-xs text-gray-600">Logged in as</p>
          <p className="text-sm font-semibold text-gray-900 truncate">{email}</p>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <div className="bg-white border-b border-gray-200 h-16 flex items-center px-8">
          <p className="text-gray-600">
            Welcome to FlyRank Usage Metering & Billing Engine
          </p>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-auto">
          <div className="p-8">
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}
