'use client'

import { useState } from 'react'
import { useLogin } from '@/lib/queries/use-auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import Link from 'next/link'
import Image from 'next/image'
import { Eye, EyeOff, ArrowRight, Shield, MapPin, BarChart3 } from 'lucide-react'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const login = useLogin()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    login.mutate({ email, password })
  }

  return (
    <div className="relative flex min-h-screen">
      {/* Left Side - Brand Panel with Gradient */}
      <div 
        className="hidden lg:flex lg:w-1/2 relative overflow-hidden"
        style={{
          background: `linear-gradient(135deg, #EA580C 0%, #F97316 50%, #FB923C 100%)`
        }}
      >
        {/* Overlay pattern */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute inset-0" style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23000000' fill-opacity='0.4'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }} />
        </div>
        
        {/* Floating elements */}
        <div className="absolute top-20 left-20 animate-float">
          <div className="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
            <MapPin className="w-8 h-8 text-white" />
          </div>
        </div>
        <div className="absolute top-40 right-32 animate-float" style={{ animationDelay: '1s' }}>
          <div className="w-14 h-14 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
            <BarChart3 className="w-7 h-7 text-white" />
          </div>
        </div>
        <div className="absolute bottom-40 left-32 animate-float" style={{ animationDelay: '2s' }}>
          <div className="w-12 h-12 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
            <Shield className="w-6 h-6 text-white" />
          </div>
        </div>

        {/* Center Logo & Brand */}
        <div className="relative z-10 flex flex-col items-center justify-center w-full px-12">
          {/* Logo */}
          <div className="mb-8 animate-slide-in-left">
            <Image 
              src="/sidewalksafety.svg" 
              alt="Sidewalk Safety" 
              width={280}
              height={70}
              className="drop-shadow-2xl"
              priority
            />
          </div>
          
          {/* Tagline */}
          <div className="text-center animate-slide-in-left" style={{ animationDelay: '100ms' }}>
            <p className="text-2xl font-light text-white/90 mb-2">
              Discover High-Value Leads
            </p>
            <p className="text-lg text-white/70">
              AI-powered parking lot condition analysis
            </p>
          </div>

          {/* Features */}
          <div className="mt-16 grid gap-4 animate-slide-in-left" style={{ animationDelay: '200ms' }}>
            <div className="flex items-center gap-3 text-white/80">
              <div className="w-2 h-2 rounded-full bg-white" />
              <span>Automated satellite imagery analysis</span>
            </div>
            <div className="flex items-center gap-3 text-white/80">
              <div className="w-2 h-2 rounded-full bg-white" />
              <span>Real-time condition scoring</span>
            </div>
            <div className="flex items-center gap-3 text-white/80">
              <div className="w-2 h-2 rounded-full bg-white" />
              <span>Business contact enrichment</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="absolute bottom-8 left-12 text-sm text-white/60">
          © 2024 Sidewalk Safety. All rights reserved.
        </div>
      </div>

      {/* Right Side - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-background relative">
        {/* Background gradient accent */}
        <div className="absolute top-0 right-0 w-1/2 h-1/2 opacity-5 pointer-events-none"
          style={{
            background: 'radial-gradient(circle at top right, #F97316 0%, transparent 70%)'
          }}
        />

        <div className="w-full max-w-md space-y-8 animate-slide-in relative z-10">
          {/* Mobile Logo */}
          <div className="lg:hidden flex justify-center mb-8">
            <Image 
              src="/sidewalksafety.svg" 
              alt="Sidewalk Safety" 
              width={200}
              height={50}
              priority
            />
          </div>

          {/* Header */}
          <div className="space-y-2">
            <h1 className="text-3xl font-bold tracking-tight text-foreground">
              Welcome back
            </h1>
            <p className="text-muted-foreground">
              Sign in to access your parking lot leads
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
              {/* Email */}
              <div className="space-y-2">
                <Label htmlFor="email" className="text-foreground font-medium">
                  Email address
                </Label>
                <Input
                  id="email"
              type="email"
                  placeholder="you@company.com"
                  autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
                  disabled={login.isPending}
              required
                  className="h-12 text-base bg-background border-border focus:border-primary focus:ring-primary"
                />
              </div>

              {/* Password */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password" className="text-foreground font-medium">
                    Password
                  </Label>
                  <button
                    type="button"
                    className="text-sm font-medium text-primary hover:text-primary/80 transition-colors"
                  >
                    Forgot password?
                  </button>
                </div>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
                    disabled={login.isPending}
              required
                    className="h-12 text-base pr-12 bg-background border-border focus:border-primary focus:ring-primary"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    tabIndex={-1}
                  >
                    {showPassword ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              disabled={login.isPending}
              className="w-full h-12 text-base font-semibold text-white shadow-lg hover:shadow-xl transition-all duration-200"
              style={{
                background: `linear-gradient(135deg, #EA580C 0%, #F97316 100%)`,
                boxShadow: '0 10px 25px -5px rgba(249, 115, 22, 0.3)',
              }}
            >
              {login.isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="h-5 w-5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Signing in...
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  Sign in
                  <ArrowRight className="h-5 w-5" />
                </span>
              )}
            </Button>
          </form>

          {/* Divider */}
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="bg-background px-4 text-muted-foreground font-medium">
                New to Sidewalk Safety?
              </span>
            </div>
          </div>

          {/* Register Link */}
          <Link href="/register">
            <Button
              variant="outline"
              className="w-full h-12 text-base font-semibold group border-border hover:border-primary hover:bg-primary/5 transition-all duration-200"
              type="button"
            >
              Create an account
              <ArrowRight className="h-5 w-5 ml-2 group-hover:translate-x-1 transition-transform" />
            </Button>
          </Link>

          {/* Footer */}
          <p className="text-center text-xs text-muted-foreground">
            By signing in, you agree to our{' '}
            <button className="underline hover:text-foreground transition-colors">
              Terms of Service
            </button>{' '}
            and{' '}
            <button className="underline hover:text-foreground transition-colors">
              Privacy Policy
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
