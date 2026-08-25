import { create } from 'zustand'
import axios from 'axios'

interface AuthState {
  isAuthenticated: boolean
  tenantId: string | null
  token: string | null
  email: string | null
  initialize: () => void
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  setTenant: (tenantId: string) => void
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  tenantId: null,
  token: null,
  email: null,

  initialize: () => {
    const token = localStorage.getItem('token')
    const tenantId = localStorage.getItem('tenantId')
    const email = localStorage.getItem('email')

    if (token && tenantId) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
      axios.defaults.headers.common['X-Tenant-ID'] = tenantId
      set({ isAuthenticated: true, token, tenantId, email })
    }
  },

  login: async (email: string, password: string) => {
    try {
      const response = await axios.post(`${API_URL}/auth/login`, {
        email,
        password,
      })

      const { access_token, tenant_id } = response.data

      localStorage.setItem('token', access_token)
      localStorage.setItem('tenantId', tenant_id)
      localStorage.setItem('email', email)

      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
      axios.defaults.headers.common['X-Tenant-ID'] = tenant_id

      set({
        isAuthenticated: true,
        token: access_token,
        tenantId: tenant_id,
        email,
      })
    } catch (error) {
      console.error('Login failed:', error)
      throw error
    }
  },

  logout: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('tenantId')
    localStorage.removeItem('email')
    delete axios.defaults.headers.common['Authorization']
    delete axios.defaults.headers.common['X-Tenant-ID']
    set({ isAuthenticated: false, token: null, tenantId: null, email: null })
  },

  setTenant: (tenantId: string) => {
    localStorage.setItem('tenantId', tenantId)
    axios.defaults.headers.common['X-Tenant-ID'] = tenantId
    set({ tenantId })
  },
}))
