'use client'

import { useEffect, useState } from 'react'
import { BACKEND_URL } from '@/lib/api/client'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { cn } from '@/lib/utils'

export function ConnectionStatus() {
  const [isOnline, setIsOnline] = useState(true)
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking')

  useEffect(() => {
    // Check browser online status
    setIsOnline(navigator.onLine)

    const handleOnline = () => setIsOnline(true)
    const handleOffline = () => setIsOnline(false)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    // Check backend status
    const checkBackend = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/health`, {
          method: 'GET',
          signal: AbortSignal.timeout(5000),
        })
        setBackendStatus(response.ok ? 'online' : 'offline')
      } catch (error) {
        setBackendStatus('offline')
      }
    }

    checkBackend()
    const interval = setInterval(checkBackend, 30000) // Check every 30 seconds

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      clearInterval(interval)
    }
  }, [])

  if (isOnline && backendStatus === 'online') {
    return null // Don't show anything if everything is fine
  }

  return (
    <Alert
      variant={backendStatus === 'offline' || !isOnline ? 'destructive' : 'default'}
      className={cn(
        'fixed bottom-4 right-4 z-50 max-w-md shadow-lg',
        backendStatus === 'checking' && 'opacity-75'
      )}
    >
      {backendStatus === 'offline' || !isOnline ? (
        <AlertCircle className="h-4 w-4" />
      ) : (
        <CheckCircle2 className="h-4 w-4" />
      )}
      <AlertTitle>
        {!isOnline
          ? 'No Internet Connection'
          : backendStatus === 'offline'
          ? 'Backend Server Offline'
          : 'Checking Connection...'}
      </AlertTitle>
      <AlertDescription>
        {!isOnline ? (
          'Please check your internet connection.'
        ) : backendStatus === 'offline' ? (
          <>
            Cannot connect to backend at <code className="text-xs">{BACKEND_URL}</code>. Please
            ensure the backend server is running.
          </>
        ) : (
          'Checking backend connection...'
        )}
      </AlertDescription>
    </Alert>
  )
}

