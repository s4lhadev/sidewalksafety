'use client'

import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { scoringPromptsApi, ScoringPrompt } from '@/lib/api/scoring-prompts'
import { cn } from '@/lib/utils'
import { 
  X, 
  Loader2, 
  MapPin, 
  CheckCircle2, 
  Hash, 
  Map as MapIcon,
  ChevronDown,
  ChevronUp,
  Search,
  Sparkles,
  RotateCcw,
  Ruler,
  Radio,
  Phone,
  Mail,
  Star,
} from 'lucide-react'
import { PropertyCategory } from '@/types'
import { DiscoveryProgress } from '@/lib/hooks/use-discovery-stream'

interface LocationInfo {
  zip?: string
  city?: string
  county?: string
  state?: string
}

interface PropCategoryOption {
  id: PropertyCategory
  label: string
  description: string
}

interface DiscoveryCardProps {
  lat: number
  lng: number
  onDiscover: (params: {
    type: 'zip' | 'county'
    value: string
    state?: string
    maxResults?: number
    scoringPrompt?: string
    propertyCategories?: PropertyCategory[]
    minAcres?: number
    maxAcres?: number
  }) => void
  onClose: () => void
  isDiscovering: boolean
  // Streaming props
  isStreaming?: boolean
  streamProgress?: DiscoveryProgress[]
  currentMessage?: DiscoveryProgress | null
}

// Default scoring prompt
const DEFAULT_SCORING_PROMPT = `Score as a lead for pavement maintenance:

HIGH (80-100): Large parking areas with visible damage, cracks, or wear
MEDIUM (40-79): Moderate paved areas, some wear visible
LOW (0-39): Small paved areas or well-maintained surfaces`

// Property categories for Regrid discovery (maps to LBCS codes)
const PROPERTY_CATEGORIES: PropCategoryOption[] = [
  { id: 'multi_family', label: 'Multi-Family', description: 'Apartments, condos, townhomes' },
  { id: 'retail', label: 'Retail', description: 'Shopping centers, stores' },
  { id: 'office', label: 'Office', description: 'Office buildings, business parks' },
  { id: 'industrial', label: 'Industrial', description: 'Warehouses, distribution' },
  { id: 'institutional', label: 'Institutional', description: 'Churches, schools, hospitals' },
]

// Default selected categories
const DEFAULT_CATEGORIES: PropertyCategory[] = ['multi_family']

export function DiscoveryCard({ 
  lat, 
  lng, 
  onDiscover, 
  onClose, 
  isDiscovering,
  isStreaming = false,
  streamProgress = [],
  currentMessage = null,
}: DiscoveryCardProps) {
  const [locationInfo, setLocationInfo] = useState<LocationInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pendingAction, setPendingAction] = useState<'zip' | 'county' | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showScoring, setShowScoring] = useState(false)
  const [maxResults, setMaxResults] = useState<number>(10)
  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(null)
  const [customPrompt, setCustomPrompt] = useState<string>('')
  const [useCustom, setUseCustom] = useState(false)
  
  // Property categories state
  const [selectedCategories, setSelectedCategories] = useState<Set<PropertyCategory>>(new Set(DEFAULT_CATEGORIES))
  
  // Size filter state
  const [minAcres, setMinAcres] = useState<string>('')
  const [maxAcres, setMaxAcres] = useState<string>('')

  // Fetch saved scoring prompts
  const { data: savedPrompts } = useQuery({
    queryKey: ['scoring-prompts'],
    queryFn: scoringPromptsApi.list,
  })

  // Set default prompt if available
  useEffect(() => {
    if (savedPrompts && savedPrompts.length > 0) {
      const defaultPrompt = savedPrompts.find(p => p.is_default)
      if (defaultPrompt && !selectedPromptId && !useCustom) {
        setSelectedPromptId(defaultPrompt.id)
      }
    }
  }, [savedPrompts, selectedPromptId, useCustom])

  useEffect(() => {
    const geocode = async () => {
      setIsLoading(true)
      setError(null)
      
      try {
        const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
        const response = await fetch(
          `https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lng}&key=${apiKey}`
        )
        const data = await response.json()
        
        if (data.status !== 'OK' || !data.results?.length) {
          setError('Location not found')
          return
        }

        const components = data.results[0].address_components || []
        const info: LocationInfo = {}

        for (const component of components) {
          if (component.types.includes('postal_code')) {
            info.zip = component.long_name
          }
          if (component.types.includes('locality')) {
            info.city = component.long_name
          }
          if (component.types.includes('administrative_area_level_2')) {
            info.county = component.long_name.replace(' County', '')
          }
          if (component.types.includes('administrative_area_level_1')) {
            info.state = component.short_name
          }
        }

        setLocationInfo(info)
      } catch (err) {
        setError('Failed to load')
      } finally {
        setIsLoading(false)
      }
    }

    geocode()
  }, [lat, lng])

  const handlePreviewZip = () => {
    if (!locationInfo?.zip) return
    setPendingAction('zip')
  }

  const handlePreviewCounty = () => {
    if (!locationInfo?.county || !locationInfo?.state) return
    setPendingAction('county')
  }

  const handleConfirm = () => {
    if (!pendingAction || !locationInfo) return
    
    // Get effective prompt: custom > selected saved prompt > undefined (uses default)
    let effectivePrompt: string | undefined = undefined
    if (useCustom && customPrompt.trim()) {
      effectivePrompt = customPrompt.trim()
    } else if (selectedPromptId && savedPrompts) {
      const selected = savedPrompts.find(p => p.id === selectedPromptId)
      if (selected) {
        effectivePrompt = selected.prompt
      }
    }
    
    // Build params - always use Regrid-first mode
    onDiscover({
      type: pendingAction,
      value: pendingAction === 'zip' ? locationInfo.zip! : locationInfo.county!,
      state: locationInfo.state,
      maxResults,
      scoringPrompt: effectivePrompt,
      propertyCategories: Array.from(selectedCategories),
      minAcres: minAcres ? parseFloat(minAcres) : undefined,
      maxAcres: maxAcres ? parseFloat(maxAcres) : undefined,
    })
  }

  const handleCancel = () => {
    setPendingAction(null)
    setShowAdvanced(false)
    setShowScoring(false)
  }

  return (
    <div className="bg-stone-50 rounded-lg shadow-lg border border-stone-200 overflow-hidden w-80 text-sm">
      {/* Header */}
      <div className="px-3 py-2 border-b border-stone-200 flex items-center justify-between bg-stone-100/80">
        <div className="flex items-center gap-2">
          <Search className="h-3.5 w-3.5 text-stone-500" />
          <span className="font-mono text-xs text-stone-500">
            {lat.toFixed(5)}, {lng.toFixed(5)}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-stone-200 transition-colors text-stone-400 hover:text-stone-600"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Content */}
      <div className="p-3">
        {/* Streaming Progress Panel */}
        {isStreaming && (
          <div className="space-y-2">
            {/* Header with live indicator */}
            <div className="flex items-center justify-between px-2 py-1.5 bg-stone-100 border border-stone-200 rounded">
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Radio className="h-3.5 w-3.5 text-amber-600" />
                  <span className="absolute -top-0.5 -right-0.5 h-1.5 w-1.5 bg-amber-500 rounded-full animate-pulse" />
                </div>
                <span className="text-[11px] font-medium text-stone-700">Discovery running</span>
              </div>
              {currentMessage?.total && currentMessage?.current && (
                <span className="text-[10px] text-stone-500 font-mono">
                  {currentMessage.current}/{currentMessage.total}
                </span>
              )}
            </div>

            {/* Progress bar */}
            {currentMessage?.total && currentMessage?.current && (
              <div className="h-1 bg-stone-200 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-amber-500 transition-all duration-300"
                  style={{ width: `${(currentMessage.current / currentMessage.total) * 100}%` }}
                />
              </div>
            )}

            {/* Progress messages - fixed height scrollable */}
            <div className="h-52 overflow-y-auto border border-stone-200 rounded bg-white">
              {streamProgress.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <div className="flex flex-col items-center gap-2">
                    <Loader2 className="h-5 w-5 animate-spin text-amber-500" />
                    <span className="text-xs text-stone-500">Starting discovery...</span>
                  </div>
                </div>
              ) : (
                <div className="p-1.5 space-y-1">
                  {streamProgress.map((msg, idx) => {
                  const isLatest = idx === streamProgress.length - 1
                  const isComplete = msg.type === 'complete'
                  const isError = msg.type === 'error'
                  const isContactFound = msg.type === 'contact_found'
                  
                  // Get status indicator
                  const getStatusDot = () => {
                    if (isComplete) return <CheckCircle2 className="h-3 w-3 text-emerald-500 shrink-0" />
                    if (isError) return <X className="h-3 w-3 text-red-500 shrink-0" />
                    if (isContactFound) return <CheckCircle2 className="h-3 w-3 text-green-500 shrink-0" />
                    if (isLatest) return <Loader2 className="h-3 w-3 animate-spin text-amber-500 shrink-0" />
                    return <span className="w-3 h-3 flex items-center justify-center text-stone-300 shrink-0">•</span>
                  }
                  
                  return (
                    <div 
                      key={idx}
                      className={cn(
                        'flex items-start gap-2 px-2 py-1 rounded text-[11px]',
                        isComplete ? 'bg-emerald-50' :
                        isError ? 'bg-red-50' :
                        isContactFound ? 'bg-green-50' :
                        isLatest ? 'bg-amber-50' :
                        'bg-transparent'
                      )}
                    >
                      <span className="mt-0.5">{getStatusDot()}</span>
                      <div className="flex-1 min-w-0">
                        <span className={cn(
                          'block leading-tight',
                          isComplete ? 'text-emerald-700 font-medium' :
                          isError ? 'text-red-600' :
                          isContactFound ? 'text-green-700' :
                          isLatest ? 'text-stone-800' : 'text-stone-500'
                        )}>
                          {msg.message}
                        </span>
                        {msg.details && (
                          <span className="block text-[10px] text-stone-400">{msg.details}</span>
                        )}
                        {isContactFound && (msg.phone || msg.email) && (
                          <div className="flex flex-wrap gap-2 mt-0.5">
                            {msg.phone && (
                              <span className="inline-flex items-center gap-1 text-[10px] text-green-600">
                                <Phone className="h-2.5 w-2.5" />
                                {msg.phone}
                              </span>
                            )}
                            {msg.email && (
                              <span className="inline-flex items-center gap-1 text-[10px] text-green-600">
                                <Mail className="h-2.5 w-2.5" />
                                {msg.email}
                              </span>
                            )}
                          </div>
                        )}
                        {isComplete && msg.stats && (
                          <div className="flex flex-wrap gap-2 mt-1 text-[10px]">
                            <span className="text-emerald-600 font-medium">{msg.stats.found} found</span>
                            <span className="text-stone-400">•</span>
                            <span className="text-emerald-600 font-medium">{msg.stats.analyzed} analyzed</span>
                            <span className="text-stone-400">•</span>
                            <span className="text-emerald-600 font-medium">{msg.stats.enriched} contacts</span>
                            {msg.stats.duration && (
                              <>
                                <span className="text-stone-400">•</span>
                                <span className="text-stone-500">{msg.stats.duration}</span>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )
                  })}
                </div>
              )}
            </div>

            {/* Close button when complete */}
            {streamProgress.some(m => m.type === 'complete' || m.type === 'error') && (
              <button
                onClick={onClose}
                className="w-full px-3 py-2 bg-stone-800 text-white rounded text-xs font-medium hover:bg-stone-700 transition-colors"
              >
                Close
              </button>
            )}
          </div>
        )}

        {/* Regular content (hidden when streaming) */}
        {!isStreaming && (
          <>
        {isLoading ? (
          <div className="flex items-center gap-2 py-3">
            <Loader2 className="h-4 w-4 animate-spin text-stone-500" />
            <span className="text-xs text-stone-500">Identifying location...</span>
          </div>
        ) : error ? (
          <div className="text-center py-3">
            <p className="text-xs text-stone-500">{error}</p>
          </div>
        ) : locationInfo ? (
          <div className="space-y-3">
            {/* Location Display */}
            <div className="space-y-1">
              {locationInfo.city && (
                <p className="text-sm font-semibold text-stone-800">{locationInfo.city}</p>
              )}
              <div className="flex items-center gap-2 flex-wrap">
              {locationInfo.zip && (
                  <span className="text-xs font-mono bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded">
                    {locationInfo.zip}
                  </span>
              )}
              {locationInfo.state && (
                  <span className="text-xs text-stone-500">{locationInfo.state}</span>
              )}
              {locationInfo.county && (
                  <span className="text-xs text-stone-400">• {locationInfo.county} County</span>
              )}
              </div>
            </div>

            {/* Confirmation State */}
            {pendingAction ? (
              <div className="space-y-3">
                {/* Selected Area */}
                <div className="flex items-center gap-2 px-2 py-1.5 bg-emerald-50 border border-emerald-200 rounded">
                  <MapIcon className="h-3.5 w-3.5 text-emerald-600" />
                  <span className="text-xs font-medium text-stone-700">
                    {pendingAction === 'zip' ? `ZIP ${locationInfo.zip}` : `${locationInfo.county} County`}
                  </span>
                  <span className="text-[10px] text-emerald-600 ml-auto">
                    {selectedCategories.size} categories
                  </span>
                </div>
                
                {/* Mode Description */}
                <p className="text-[10px] text-stone-400 leading-tight px-0.5">
                  Discover properties via Regrid parcel data, analyze with satellite imagery, and find decision-maker contacts.
                </p>

                {/* Max Results */}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-stone-500">Max results</span>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={maxResults}
                    onChange={(e) => setMaxResults(Math.max(1, Math.min(50, parseInt(e.target.value) || 1)))}
                    className="w-14 px-2 py-1 text-xs font-mono border border-stone-200 rounded focus:ring-1 focus:ring-stone-400 focus:border-stone-400 text-center bg-white"
                  />
                </div>

                {/* Property Categories */}
                <div>
                  <button
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="w-full flex items-center justify-between px-2 py-1.5 bg-emerald-50 border border-emerald-200 rounded hover:bg-emerald-100 transition-colors"
                  >
                    <div className="flex items-center gap-1.5">
                      <MapIcon className="h-3.5 w-3.5 text-emerald-600" />
                      <span className="text-xs font-medium text-emerald-700">Property Types</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] text-emerald-600">{selectedCategories.size} selected</span>
                      {showAdvanced ? (
                        <ChevronUp className="h-3.5 w-3.5 text-emerald-500" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5 text-emerald-500" />
                      )}
                    </div>
                  </button>
                  
                  {showAdvanced && (
                    <div className="mt-2 p-2 border border-emerald-200 rounded bg-white space-y-1">
                      {PROPERTY_CATEGORIES.map((cat) => (
                        <label 
                          key={cat.id}
                          className="flex items-start gap-2 cursor-pointer hover:bg-emerald-50 px-1.5 py-1.5 rounded"
                        >
                          <input
                            type="checkbox"
                            checked={selectedCategories.has(cat.id)}
                            onChange={() => {
                              const newSelected = new Set(selectedCategories)
                              if (newSelected.has(cat.id)) {
                                newSelected.delete(cat.id)
                              } else {
                                newSelected.add(cat.id)
                              }
                              setSelectedCategories(newSelected)
                            }}
                            className="w-3 h-3 mt-0.5 rounded border-stone-300 text-emerald-600 focus:ring-emerald-500"
                          />
                          <div className="flex-1 min-w-0">
                            <span className="text-[11px] font-medium text-stone-700 block">{cat.label}</span>
                            <span className="text-[10px] text-stone-400 block">{cat.description}</span>
                          </div>
                        </label>
                      ))}
                    </div>
                  )}
                  
                  {/* Size Filter */}
                  <div className="mt-3 pt-3 border-t border-emerald-200">
                    <div className="flex items-center gap-2 mb-2">
                      <Ruler className="h-3.5 w-3.5 text-emerald-600" />
                      <span className="text-[11px] font-medium text-emerald-700">Size Filter (acres)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1">
                        <input
                          type="number"
                          min={0}
                          step={0.1}
                          placeholder="Min"
                          value={minAcres}
                          onChange={(e) => setMinAcres(e.target.value)}
                          className="w-full px-2 py-1.5 text-xs font-mono border border-emerald-200 rounded focus:ring-1 focus:ring-emerald-400 focus:border-emerald-400 text-center bg-white placeholder:text-stone-300"
                        />
                      </div>
                      <span className="text-[10px] text-stone-400">to</span>
                      <div className="flex-1">
                        <input
                          type="number"
                          min={0}
                          step={0.1}
                          placeholder="Max"
                          value={maxAcres}
                          onChange={(e) => setMaxAcres(e.target.value)}
                          className="w-full px-2 py-1.5 text-xs font-mono border border-emerald-200 rounded focus:ring-1 focus:ring-emerald-400 focus:border-emerald-400 text-center bg-white placeholder:text-stone-300"
                        />
                      </div>
                    </div>
                    <p className="text-[9px] text-emerald-500 mt-1">Leave empty for no limit</p>
                  </div>
                </div>

                {/* Scoring Criteria */}
                <div>
                  <button
                    onClick={() => setShowScoring(!showScoring)}
                    className="w-full flex items-center justify-between px-2 py-1.5 bg-violet-50 border border-violet-200 rounded hover:bg-violet-100 transition-colors"
                  >
                    <div className="flex items-center gap-1.5">
                      <Sparkles className="h-3.5 w-3.5 text-violet-500" />
                      <span className="text-xs font-medium text-violet-700">AI Scoring Criteria</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {useCustom ? (
                        <span className="text-[10px] text-violet-600 font-medium">Custom</span>
                      ) : selectedPromptId && savedPrompts ? (
                        <span className="text-[10px] text-violet-600 font-medium">
                          {savedPrompts.find(p => p.id === selectedPromptId)?.title || 'Selected'}
                        </span>
                      ) : (
                        <span className="text-[10px] text-violet-400">Default</span>
                      )}
                      {showScoring ? (
                        <ChevronUp className="h-3.5 w-3.5 text-violet-400" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5 text-violet-400" />
                      )}
                    </div>
                  </button>

                  {showScoring && (
                    <div className="mt-2 space-y-2">
                      {/* Saved Prompts Selector */}
                      {savedPrompts && savedPrompts.length > 0 && (
                        <div>
                          <label className="block text-[10px] font-medium text-stone-600 mb-1.5">
                            Saved Prompts
                          </label>
                          <div className="space-y-1">
                            {savedPrompts.map((prompt) => (
                              <button
                                key={prompt.id}
                                onClick={() => {
                                  setSelectedPromptId(prompt.id)
                                  setUseCustom(false)
                                }}
                                className={cn(
                                  'w-full flex items-center justify-between px-2 py-1.5 rounded text-left transition-colors',
                                  selectedPromptId === prompt.id && !useCustom
                                    ? 'bg-violet-100 border border-violet-300'
                                    : 'bg-stone-50 border border-stone-200 hover:bg-stone-100'
                                )}
                              >
                                <div className="flex items-center gap-2 min-w-0 flex-1">
                                  {prompt.is_default && (
                                    <Star className="h-3 w-3 text-amber-500 fill-current shrink-0" />
                                  )}
                                  <span className="text-[11px] font-medium text-stone-700 truncate">
                                    {prompt.title}
                                  </span>
                                </div>
                                {selectedPromptId === prompt.id && !useCustom && (
                                  <CheckCircle2 className="h-3.5 w-3.5 text-violet-600 shrink-0" />
                                )}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Custom Prompt Option */}
                      <div>
                        <div className="flex items-center justify-between mb-1.5">
                          <label className="text-[10px] font-medium text-stone-600">
                            Custom Criteria
                          </label>
                          <button
                            onClick={() => {
                              setUseCustom(!useCustom)
                              if (!useCustom) {
                                setSelectedPromptId(null)
                              }
                            }}
                            className={cn(
                              'text-[10px] font-medium transition-colors',
                              useCustom ? 'text-violet-600' : 'text-stone-400 hover:text-stone-600'
                            )}
                          >
                            {useCustom ? 'Using Custom' : 'Use Custom'}
                          </button>
                        </div>
                        <textarea
                          value={customPrompt}
                          onChange={(e) => setCustomPrompt(e.target.value)}
                          placeholder={DEFAULT_SCORING_PROMPT}
                          disabled={!useCustom}
                          className={cn(
                            'w-full h-24 px-2 py-1.5 text-[11px] border rounded resize-none transition-colors',
                            useCustom
                              ? 'border-violet-300 focus:ring-1 focus:ring-violet-400 focus:border-violet-400 bg-white'
                              : 'border-stone-200 bg-stone-50 text-stone-400'
                          )}
                        />
                        {useCustom && customPrompt.trim() && (
                          <button
                            onClick={() => {
                              setCustomPrompt('')
                              setUseCustom(false)
                              if (savedPrompts && savedPrompts.length > 0) {
                                const defaultPrompt = savedPrompts.find(p => p.is_default)
                                if (defaultPrompt) {
                                  setSelectedPromptId(defaultPrompt.id)
                                }
                              }
                            }}
                            className="mt-1 flex items-center gap-1 text-[10px] text-stone-500 hover:text-stone-700"
                          >
                            <RotateCcw className="h-3 w-3" />
                            Reset to Default
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={handleCancel}
                    className="flex-1 px-3 py-2 bg-stone-200 text-stone-600 rounded text-xs font-medium hover:bg-stone-300 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleConfirm}
                    disabled={isDiscovering || selectedCategories.size === 0}
                    className="flex-1 px-3 py-2 rounded text-xs font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5 bg-emerald-600 text-white hover:bg-emerald-700"
                  >
                    {isDiscovering ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Starting...</span>
                      </>
                    ) : (
                      <>
                        <Search className="h-3.5 w-3.5" />
                        <span>Find Properties</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              /* Initial Action Buttons */
              <div className="flex gap-2">
                {locationInfo.zip && (
                  <button
                    onClick={handlePreviewZip}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-stone-800 text-white rounded text-xs font-medium hover:bg-stone-700 transition-colors"
                  >
                    <Hash className="h-3.5 w-3.5" />
                    <span>ZIP {locationInfo.zip}</span>
                  </button>
                )}

                {locationInfo.county && locationInfo.state && (
                  <button
                    onClick={handlePreviewCounty}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-stone-200 text-stone-700 rounded text-xs font-medium hover:bg-stone-300 transition-colors"
                  >
                    <MapIcon className="h-3.5 w-3.5" />
                    <span>County</span>
                  </button>
                )}
              </div>
            )}
          </div>
        ) : null}
          </>
        )}
      </div>
    </div>
  )
}
