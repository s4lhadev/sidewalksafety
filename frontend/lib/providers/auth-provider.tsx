'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { User } from '@/types'
import { authApi } from '@/lib/api/auth'

interface AuthContextType {
  user: User | null
  token: string | null
  login: (token: string, user: User) => void
  logout: () => void
  isAuthenticated: boolean
  isLoading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const TOKEN_EXPIRY_KEY = 'auth_token_expiry'
const TOKEN_KEY = 'auth_token'
const USER_KEY = 'auth_user'
const TOKEN_DURATION_MS = 24 * 60 * 60 * 1000 // 24 hours in milliseconds

function isTokenExpired(): boolean {
  if (typeof window === 'undefined') return true
  
  const expiryTime = localStorage.getItem(TOKEN_EXPIRY_KEY)
  if (!expiryTime) return true
  
  const expiry = parseInt(expiryTime, 10)
  return Date.now() >= expiry
}

function clearAuthData() {
  if (typeof window === 'undefined') return
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  localStorage.removeItem(TOKEN_EXPIRY_KEY)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    function restoreSession() {
      if (typeof window === 'undefined') {
        setIsLoading(false)
        return
      }

      const storedToken = localStorage.getItem(TOKEN_KEY)
      const storedUser = localStorage.getItem(USER_KEY)
      const storedExpiry = localStorage.getItem(TOKEN_EXPIRY_KEY)

      // If token exists but no expiry, set expiry to 24h from now (for existing sessions)
      if (storedToken && !storedExpiry) {
        const expiryTime = Date.now() + TOKEN_DURATION_MS
        localStorage.setItem(TOKEN_EXPIRY_KEY, expiryTime.toString())
      }

      // Check if token exists and is not expired locally
      if (storedToken && storedUser && !isTokenExpired()) {
        // Restore session from localStorage immediately
        // Don't validate on mount - let actual API calls handle validation
        // This prevents 401 errors on reload from logging users out
        setToken(storedToken)
        try {
          const parsedUser = JSON.parse(storedUser)
          setUser(parsedUser)
        } catch {
          // Invalid user data, clear everything
          clearAuthData()
          setToken(null)
          setUser(null)
        }
      } else {
        // Token expired locally or doesn't exist, clear everything
        if (storedToken && isTokenExpired()) {
          clearAuthData()
        }
        setToken(null)
        setUser(null)
      }

      setIsLoading(false)
    }

    restoreSession()
  }, [])

  const login = (newToken: string, newUser: User) => {
    const expiryTime = Date.now() + TOKEN_DURATION_MS
    
    setToken(newToken)
    setUser(newUser)
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(USER_KEY, JSON.stringify(newUser))
    localStorage.setItem(TOKEN_EXPIRY_KEY, expiryTime.toString())
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    clearAuthData()
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        logout,
        isAuthenticated: !!token && !!user,
        isLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

