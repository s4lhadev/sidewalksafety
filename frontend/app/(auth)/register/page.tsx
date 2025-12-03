'use client'

import { useState } from 'react'
import { useRegister } from '@/lib/queries/use-auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import Link from 'next/link'
import Image from 'next/image'
import { Eye, EyeOff, ArrowRight, ArrowLeft, Building2, Zap, Target } from 'lucide-react'

export default function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [phone, setPhone] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const register = useRegister()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    register.mutate({
      email,
      password,
      company_name: companyName,
      phone: phone || undefined,
    })
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
        <div className="absolute top-24 right-24 animate-float">
          <div className="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
            <Building2 className="w-8 h-8 text-white" />
          </div>
        </div>
        <div className="absolute top-48 left-24 animate-float" style={{ animationDelay: '1.5s' }}>
          <div className="w-14 h-14 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
            <Zap className="w-7 h-7 text-white" />
          </div>
        </div>
        <div className="absolute bottom-32 right-40 animate-float" style={{ animationDelay: '0.8s' }}>
          <div className="w-12 h-12 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
            <Target className="w-6 h-6 text-white" />
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
              Start Finding Leads Today
            </p>
            <p className="text-lg text-white/70">
              Join hundreds of pavement companies
            </p>
          </div>

          {/* Benefits */}
          <div className="mt-16 grid gap-4 animate-slide-in-left" style={{ animationDelay: '200ms' }}>
            <div className="flex items-center gap-3 text-white/80">
              <div className="w-2 h-2 rounded-full bg-white" />
              <span>Free trial with 50 parking lots</span>
            </div>
            <div className="flex items-center gap-3 text-white/80">
              <div className="w-2 h-2 rounded-full bg-white" />
              <span>No credit card required</span>
            </div>
            <div className="flex items-center gap-3 text-white/80">
              <div className="w-2 h-2 rounded-full bg-white" />
              <span>Cancel anytime</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="absolute bottom-8 left-12 text-sm text-white/60">
          © 2024 Sidewalk Safety. All rights reserved.
        </div>
      </div>

      {/* Right Side - Register Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-background relative">
        {/* Background gradient accent */}
        <div className="absolute top-0 right-0 w-1/2 h-1/2 opacity-5 pointer-events-none"
          style={{
            background: 'radial-gradient(circle at top right, #F97316 0%, transparent 70%)'
          }}
        />

        <div className="w-full max-w-md space-y-6 animate-slide-in relative z-10">
          {/* Mobile Logo */}
          <div className="lg:hidden flex justify-center mb-6">
            <Image 
              src="/sidewalksafety.svg" 
              alt="Sidewalk Safety" 
              width={200}
              height={50}
              priority
            />
          </div>

          {/* Back to Login */}
          <Link 
            href="/login" 
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to sign in
          </Link>

          {/* Header */}
          <div className="space-y-2">
            <h1 className="text-3xl font-bold tracking-tight text-foreground">
              Create your account
            </h1>
            <p className="text-muted-foreground">
              Start discovering high-value parking lot leads
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-4">
              {/* Company Name */}
              <div className="space-y-2">
                <Label htmlFor="company" className="text-foreground font-medium">
                  Company name
                </Label>
                <Input
                  id="company"
                  type="text"
                  placeholder="Acme Paving Co."
                  autoComplete="organization"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  disabled={register.isPending}
                  required
                  className="h-12 text-base bg-background border-border focus:border-primary focus:ring-primary"
                />
              </div>

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
                  disabled={register.isPending}
                  required
                  className="h-12 text-base bg-background border-border focus:border-primary focus:ring-primary"
                />
              </div>

              {/* Password */}
              <div className="space-y-2">
                <Label htmlFor="password" className="text-foreground font-medium">
                  Password
                </Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Create a strong password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={register.isPending}
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

              {/* Phone */}
              <div className="space-y-2">
                <Label htmlFor="phone" className="text-foreground font-medium">
                  Phone number <span className="text-muted-foreground font-normal">(optional)</span>
                </Label>
                <Input
                  id="phone"
                  type="tel"
                  placeholder="+1 (555) 000-0000"
                  autoComplete="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  disabled={register.isPending}
                  className="h-12 text-base bg-background border-border focus:border-primary focus:ring-primary"
                />
              </div>
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              disabled={register.isPending}
              className="w-full h-12 text-base font-semibold text-white shadow-lg hover:shadow-xl transition-all duration-200"
              style={{
                background: `linear-gradient(135deg, #EA580C 0%, #F97316 100%)`,
                boxShadow: '0 10px 25px -5px rgba(249, 115, 22, 0.3)',
              }}
            >
              {register.isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="h-5 w-5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Creating account...
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  Create account
                  <ArrowRight className="h-5 w-5" />
                </span>
              )}
            </Button>
          </form>

          {/* Footer */}
          <p className="text-center text-xs text-muted-foreground pt-2">
            By creating an account, you agree to our{' '}
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
