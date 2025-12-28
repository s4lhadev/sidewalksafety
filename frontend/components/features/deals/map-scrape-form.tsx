'use client'

import { useState } from 'react'
import { useScrapeDeals } from '@/lib/queries/use-deals'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Plus, MapPin, Loader2, Sparkles } from 'lucide-react'

interface MapScrapeFormProps {
  onScrapeComplete?: () => void
}

export function MapScrapeForm({ onScrapeComplete }: MapScrapeFormProps) {
  const [open, setOpen] = useState(false)
  const [areaType, setAreaType] = useState<'zip' | 'county'>('zip')
  const [value, setValue] = useState('')
  const [state, setState] = useState('')
  const [maxDeals, setMaxDeals] = useState(10)

  const scrapeDeals = useScrapeDeals()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    scrapeDeals.mutate(
      {
        area_type: areaType,
        value,
        state: areaType === 'county' ? state : undefined,
        max_results: maxDeals,
      },
      {
        onSuccess: () => {
          setOpen(false)
          setValue('')
          setState('')
          onScrapeComplete?.()
        },
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button 
          className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-orange-500 to-orange-600 text-white rounded-xl shadow-lg hover:shadow-xl hover:from-orange-600 hover:to-orange-700 transition-all font-medium text-sm"
          style={{ boxShadow: '0 8px 20px -4px rgba(249, 115, 22, 0.4)' }}
        >
          <Plus className="h-4 w-4" />
          Discover Area
        </button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-3 mb-1">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div>
              <DialogTitle className="text-lg">Discover Parking Lots</DialogTitle>
              <DialogDescription className="text-sm">
                AI-powered discovery in your target area
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-5 mt-4">
          {/* Area Type Toggle */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">Search by</Label>
            <div className="flex gap-2 p-1 bg-muted rounded-lg">
              <button
                type="button"
                onClick={() => setAreaType('zip')}
                className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  areaType === 'zip'
                    ? 'bg-background shadow text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                ZIP Code
              </button>
              <button
                type="button"
                onClick={() => setAreaType('county')}
                className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  areaType === 'county'
                    ? 'bg-background shadow text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                County
              </button>
            </div>
          </div>

          {/* Location Input */}
          {areaType === 'zip' ? (
            <div className="space-y-2">
              <Label htmlFor="zip">ZIP Code</Label>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="zip"
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  required
                  placeholder="90210"
                  className="pl-10 h-11"
                />
              </div>
            </div>
          ) : (
            <div className="grid gap-4">
              <div className="space-y-2">
                <Label htmlFor="county">County</Label>
                <div className="relative">
                  <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="county"
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    required
                    placeholder="Los Angeles"
                    className="pl-10 h-11"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="state">State</Label>
                <Input
                  id="state"
                  value={state}
                  onChange={(e) => setState(e.target.value)}
                  required
                  placeholder="CA"
                  className="h-11"
                  maxLength={2}
                />
              </div>
            </div>
          )}

          {/* Max Results */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="maxDeals">Max parking lots</Label>
              <span className="text-xs text-muted-foreground">Cost control</span>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="range"
                id="maxDeals"
                min={5}
                max={50}
                step={5}
                value={maxDeals}
                onChange={(e) => setMaxDeals(parseInt(e.target.value))}
                className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
              />
              <span className="w-12 text-center text-sm font-medium bg-muted px-2 py-1 rounded-md">
                {maxDeals}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              Higher limits use more API credits
            </p>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              className="flex-1 sm:flex-none"
            >
              Cancel
            </Button>
            <Button 
              type="submit" 
              disabled={scrapeDeals.isPending}
              className="flex-1 sm:flex-none bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700"
            >
              {scrapeDeals.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Discovering...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Start Discovery
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
