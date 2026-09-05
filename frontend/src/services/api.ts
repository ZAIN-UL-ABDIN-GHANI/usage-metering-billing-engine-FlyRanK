import axios, { AxiosInstance } from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

const client: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')

  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('tenantId')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export interface UsageData {
  api_calls_used: number
  api_calls_limit: number
  ai_tokens_used: number
  ai_tokens_limit: number
  current_cost: number
  billing_period_start: string
  billing_period_end: string
  plan_name: string
}

export interface SubscriptionData {
  plan_name: string
  status: string
  current_period_start: string
  current_period_end: string
  renewal_date: string
}

export interface BillableRequest {
  type: 'api_call' | 'ai_tokens'
  quantity?: number
}

export const apiService = {
  // Usage
  getUsage: async (): Promise<UsageData> => {
    const response = await client.get('/usage')
    return response.data
  },

  // Generate (dummy billable endpoint)
  generate: async (data: {
    prompt: string
    token_count?: number
  }): Promise<{ result: string; tokens_used: number; cost: number }> => {
    const response = await client.post('/generate', data)
    return response.data
  },

  // Billing
  getSubscription: async (): Promise<SubscriptionData> => {
    const response = await client.get('/subscription')
    return response.data
  },

  createCheckoutSession: async (planId: string): Promise<string> => {
    const response = await client.post('/checkout', { plan_id: planId })
    return response.data.session_id
  },

  upgradeToProViaCheckout: async (): Promise<{ session_id: string }> => {
    const response = await client.post('/checkout', {
      plan_id: 'pro',
    })
    return response.data
  },

  // Plan info
  getPlans: async (): Promise<any[]> => {
    const response = await client.get('/plans')
    return response.data
  },

  // Auth
  logout: async (): Promise<void> => {
    await client.post('/auth/logout')
  },

  // Health check
  health: async (): Promise<{ status: string }> => {
    const response = await client.get('/health')
    return response.data
  },
}
