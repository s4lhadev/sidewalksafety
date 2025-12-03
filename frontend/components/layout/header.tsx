'use client'

import { useState } from 'react'
import { useAuth } from '@/lib/providers/auth-provider'
import { Button } from '@/components/ui/button'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import { 
  LogOut, 
  User, 
  Settings, 
  ChevronDown,
  MapPin,
  BarChart3,
  Bell,
  HelpCircle
} from 'lucide-react'

export function Header() {
  const { user, logout } = useAuth()
  const router = useRouter()
  const [showUserMenu, setShowUserMenu] = useState(false)

  const handleLogout = () => {
    logout()
    router.push('/login')
  }

  return (
    <header className="sticky top-0 z-50 w-full bg-background border-b border-border/50">
      <div className="flex h-14 items-center justify-between px-4">
        {/* Left: Logo & Navigation */}
        <div className="flex items-center gap-8">
          {/* Logo */}
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => router.push('/dashboard')}>
            <Image 
              src="/sidewalksafety.svg" 
              alt="Sidewalk Safety" 
              width={140}
              height={32}
              className="h-8 w-auto"
            />
          </div>

          {/* Primary Navigation */}
          <nav className="hidden md:flex items-center gap-1">
            <NavItem 
              icon={<MapPin className="h-4 w-4" />} 
              label="Discover" 
              active 
              onClick={() => router.push('/dashboard')}
            />
            <NavItem 
              icon={<BarChart3 className="h-4 w-4" />} 
              label="Analytics" 
              onClick={() => {}}
            />
          </nav>
        </div>

        {/* Right: Actions & User */}
        <div className="flex items-center gap-2">
          {/* Notifications */}
          <Button variant="ghost" size="icon" className="h-9 w-9 text-muted-foreground hover:text-foreground">
            <Bell className="h-4 w-4" />
          </Button>

          {/* Help */}
          <Button variant="ghost" size="icon" className="h-9 w-9 text-muted-foreground hover:text-foreground">
            <HelpCircle className="h-4 w-4" />
          </Button>

          {/* Divider */}
          <div className="h-6 w-px bg-border mx-2" />

          {/* User Menu */}
          {user && (
            <div className="relative">
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-muted transition-colors"
              >
                <div className="h-8 w-8 rounded-full bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center text-white font-medium text-sm">
                  {user.company_name?.charAt(0)?.toUpperCase() || 'U'}
                </div>
                <div className="hidden sm:block text-left">
                  <p className="text-sm font-medium text-foreground leading-tight">
                    {user.company_name}
                  </p>
                  <p className="text-xs text-muted-foreground leading-tight">
                    {user.email}
                  </p>
                </div>
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              </button>

              {/* Dropdown */}
              {showUserMenu && (
                <>
                  <div 
                    className="fixed inset-0 z-40" 
                    onClick={() => setShowUserMenu(false)} 
                  />
                  <div className="absolute right-0 top-full mt-2 w-56 bg-card border border-border rounded-lg shadow-lg overflow-hidden z-50 animate-slide-in">
                    <div className="p-3 border-b border-border">
                      <p className="text-sm font-medium">{user.company_name}</p>
                      <p className="text-xs text-muted-foreground">{user.email}</p>
                    </div>
                    <div className="p-1">
                      <MenuButton icon={<User className="h-4 w-4" />} label="Profile" />
                      <MenuButton icon={<Settings className="h-4 w-4" />} label="Settings" />
                    </div>
                    <div className="p-1 border-t border-border">
                      <MenuButton 
                        icon={<LogOut className="h-4 w-4" />} 
                        label="Sign out" 
                        onClick={handleLogout}
                        danger
                      />
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

function NavItem({ 
  icon, 
  label, 
  active, 
  onClick 
}: { 
  icon: React.ReactNode
  label: string
  active?: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`
        flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors
        ${active 
          ? 'bg-primary/10 text-primary' 
          : 'text-muted-foreground hover:text-foreground hover:bg-muted'
        }
      `}
    >
      {icon}
      {label}
    </button>
  )
}

function MenuButton({ 
  icon, 
  label, 
  onClick,
  danger
}: { 
  icon: React.ReactNode
  label: string
  onClick?: () => void
  danger?: boolean
}) {
  return (
    <button
      onClick={onClick}
      className={`
        w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors
        ${danger 
          ? 'text-destructive hover:bg-destructive/10' 
          : 'text-foreground hover:bg-muted'
        }
      `}
    >
      {icon}
      {label}
    </button>
  )
}
