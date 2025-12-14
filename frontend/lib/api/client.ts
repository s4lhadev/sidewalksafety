import axios, { AxiosError, AxiosInstance } from 'axios'
import { ApiError } from '@/types'

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
const API_BASE_URL = `${BACKEND_URL}/api/v1`

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
})

apiClient.interceptors.request.use(
  (config) => {
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type']
    }

    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('auth_token')
      const isAuthEndpoint = config.url?.includes('/auth/')

      // Always attach token if it exists - let the backend validate it
      // Don't check expiration here as auth provider handles session restoration
      if (!isAuthEndpoint && token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        const isAuthEndpoint = error.config?.url?.includes('/auth/')
        
        // Don't clear auth data or redirect for /auth/me during initialization
        // The auth provider handles session restoration, and clearing here causes logout on reload
        if (isAuthEndpoint && error.config?.url?.includes('/auth/me')) {
          // Just reject the error, don't clear localStorage
          return Promise.reject(error)
        }
        
        // For other 401s, clear auth data and redirect
        localStorage.removeItem('auth_token')
        localStorage.removeItem('auth_user')
        localStorage.removeItem('auth_token_expiry')
        
        // Only redirect if not already on auth endpoint
        if (!isAuthEndpoint) {
          window.location.href = '/login'
        }
      }
    }

    return Promise.reject(error)
  }
)

export { apiClient, API_BASE_URL, BACKEND_URL }

