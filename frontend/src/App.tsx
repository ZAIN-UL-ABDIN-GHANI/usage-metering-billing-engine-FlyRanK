import React, { useEffect } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import UsageDetail from './pages/UsageDetail'
import Plans from './pages/Plans'
import Checkout from './pages/Checkout'
import UpgradeSuccess from './pages/UpgradeSuccess'
import Settings from './pages/Settings'
import DocsPage from './pages/DocsPage'
import './App.css'

export default function App() {
  const { isAuthenticated, initialize } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    initialize()
  }, [initialize])

  if (!isAuthenticated) {
    return <Login />
  }

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/usage" element={<UsageDetail />} />
        <Route path="/plans" element={<Plans />} />
        <Route path="/checkout" element={<Checkout />} />
        <Route path="/upgrade-success" element={<UpgradeSuccess />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/docs" element={<DocsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}
