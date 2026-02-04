'use client'

import { useState, useCallback, useEffect, useMemo } from 'react'
import { 
  Search, X, Hexagon, Loader2, ChevronDown, ChevronUp, 
  MapPin, Compass, CheckCircle2, Square, SquareCheck, 
  ArrowRight, Building2, Star, Phone, Globe, Hash
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { PlaceWithParcel, ProcessingProgress, ProcessedPlace } from '@/lib/api/discovery'

// Urban area info type
interface UrbanAreaInfo {
  id: string
  name: string
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon
}

// ZIP info type
interface ZipInfo {
  id: string
  code: string
  name: string
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon
}

interface DiscoveryPanelProps {
  // Urban area selection
  onShowUrbanOverlay?: (show: boolean) => void
  onUrbanAreaSelect?: (urbanArea: UrbanAreaInfo | null) => void
  selectedUrbanArea?: UrbanAreaInfo | null
  
  // ZIP selection within urban area
  onShowZipsInUrban?: (show: boolean) => void
  onZipSelect?: (zip: ZipInfo | null) => void
  selectedZip?: ZipInfo | null
  
  // Drawing
  onDrawPolygon: () => void
  onCancelDrawing?: () => void
  onClearDrawnPolygon?: () => void
  isDrawing: boolean
  drawnPolygon: GeoJSON.Polygon | null
  
  // Places discovery
  onDiscoverPlaces: (geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon, propertyType: string) => void
  isDiscovering: boolean
  discoveredPlaces: PlaceWithParcel[]
  
  // Selection
  selectedPlaces: PlaceWithParcel[]
  onPlaceSelect: (place: PlaceWithParcel, selected: boolean) => void
  onSelectAll: () => void
  onDeselectAll: () => void
  
  // Processing
  onProcessSelected: (places: PlaceWithParcel[]) => void
  isProcessing?: boolean
  processingProgress?: ProcessingProgress | null
  processedResults?: ProcessedPlace[]
  
  // Clear/Reset
  onClear?: () => void
}

type Step = 'urban' | 'zip' | 'area_choice' | 'property_type' | 'results'
type AreaChoice = 'draw' | 'entire_zip' | null

export function DiscoveryPanel({
  onShowUrbanOverlay,
  onUrbanAreaSelect,
  selectedUrbanArea,
  onShowZipsInUrban,
  onZipSelect,
  selectedZip,
  onDrawPolygon,
  onCancelDrawing,
  onClearDrawnPolygon,
  isDrawing,
  drawnPolygon,
  onDiscoverPlaces,
  isDiscovering,
  discoveredPlaces,
  isProcessing = false,
  processingProgress,
  processedResults = [],
  selectedPlaces,
  onPlaceSelect,
  onSelectAll,
  onDeselectAll,
  onProcessSelected,
  onClear,
}: DiscoveryPanelProps) {
  const [isExpanded, setIsExpanded] = useState(true)
  const [step, setStep] = useState<Step>('urban')
  const [areaChoice, setAreaChoice] = useState<AreaChoice>(null)
  const [propertyType, setPropertyType] = useState('')

  // Selected area geometry (either drawn polygon or ZIP boundary)
  const selectedAreaGeometry = useMemo(() => {
    if (areaChoice === 'draw' && drawnPolygon) return drawnPolygon
    if (areaChoice === 'entire_zip' && selectedZip?.geometry) return selectedZip.geometry
    return null
  }, [areaChoice, drawnPolygon, selectedZip])

  // Handle urban area continue -> show ZIPs
  const handleUrbanContinue = useCallback(() => {
    setStep('zip')
    onShowUrbanOverlay?.(false)
    onShowZipsInUrban?.(true)
  }, [onShowUrbanOverlay, onShowZipsInUrban])

  // Handle ZIP continue -> choose draw or entire
  const handleZipContinue = useCallback(() => {
    setStep('area_choice')
    onShowZipsInUrban?.(false)
  }, [onShowZipsInUrban])

  // Handle area choice selection
  const handleAreaChoice = useCallback((choice: AreaChoice) => {
    setAreaChoice(choice)
    if (choice === 'draw') {
      onDrawPolygon()
    } else if (choice === 'entire_zip') {
      // Go directly to property type
      setStep('property_type')
    }
  }, [onDrawPolygon])

  // Handle drawing complete -> go to property type
  useEffect(() => {
    if (drawnPolygon && step === 'area_choice' && areaChoice === 'draw') {
      setStep('property_type')
    }
  }, [drawnPolygon, step, areaChoice])

  // Handle search
  const handleSearch = useCallback(() => {
    if (!selectedAreaGeometry || !propertyType.trim()) return
    onDiscoverPlaces(selectedAreaGeometry, propertyType.trim())
    setStep('results')
  }, [selectedAreaGeometry, propertyType, onDiscoverPlaces])

  // Handle process
  const handleProcess = useCallback(() => {
    if (selectedPlaces.length > 0) {
      onProcessSelected(selectedPlaces)
    }
  }, [selectedPlaces, onProcessSelected])

  // Handle back navigation
  const handleBack = useCallback(() => {
    switch (step) {
      case 'zip':
        setStep('urban')
        onZipSelect?.(null)  // Clear selected ZIP
        onShowZipsInUrban?.(false)
        onShowUrbanOverlay?.(true)
        break
      case 'area_choice':
        setStep('zip')
        setAreaChoice(null)
        onClearDrawnPolygon?.()
        onZipSelect?.(null)  // Clear selected ZIP when going back to ZIP selection
        onShowZipsInUrban?.(true)
        break
      case 'property_type':
        setStep('area_choice')
        setPropertyType('')
        if (areaChoice === 'draw') {
          onClearDrawnPolygon?.()
        }
        break
      case 'results':
        setStep('property_type')
        onDeselectAll()
        break
    }
  }, [step, areaChoice, onShowUrbanOverlay, onShowZipsInUrban, onClearDrawnPolygon, onDeselectAll, onZipSelect])

  // Handle clear/reset
  const handleClear = useCallback(() => {
    setStep('urban')
    setAreaChoice(null)
    setPropertyType('')
    onUrbanAreaSelect?.(null)
    onZipSelect?.(null)
    onClearDrawnPolygon?.()
    onDeselectAll()
    onShowUrbanOverlay?.(true)
    onShowZipsInUrban?.(false)
    onClear?.()
  }, [onUrbanAreaSelect, onZipSelect, onClearDrawnPolygon, onDeselectAll, onShowUrbanOverlay, onShowZipsInUrban, onClear])

  // Urban overlay control on mount
  useEffect(() => {
    if (isExpanded && step === 'urban') {
      onShowUrbanOverlay?.(true)
    }
  }, [isExpanded, step, onShowUrbanOverlay])

  // ESC key handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (isDrawing) {
          onCancelDrawing?.()
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isDrawing, onCancelDrawing])

  return (
    <div className="absolute top-4 right-4 z-20 w-80">
      <div className="bg-white/95 backdrop-blur-sm rounded-lg shadow-lg border border-stone-200 overflow-hidden">
        {/* Header */}
        <div className="px-3 py-2.5 border-b border-stone-100 bg-stone-50/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Search className="h-3.5 w-3.5 text-stone-400" />
              <span className="text-xs font-semibold text-stone-700 uppercase tracking-wider">
                Find Properties
              </span>
            </div>
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1 hover:bg-stone-200/50 rounded transition-colors"
            >
              {isExpanded ? (
                <ChevronUp className="h-3.5 w-3.5 text-stone-400" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5 text-stone-400" />
              )}
            </button>
          </div>
        </div>

        {/* Content */}
        {isExpanded && (
          <div className="p-3 max-h-[70vh] overflow-y-auto">
            
            {/* Step 1: Urban Area Selection */}
            {step === 'urban' && (
              <div className="space-y-3">
                {!selectedUrbanArea ? (
                  <>
                    <p className="text-[10px] font-semibold text-stone-500 uppercase tracking-wider">
                      Step 1: Select Metro Area
                    </p>
                    <div className="p-3 bg-stone-50 rounded-md border border-stone-200">
                      <div className="flex flex-col items-center gap-2 text-center">
                        <Compass className="h-8 w-8 text-indigo-500" />
                        <p className="text-xs font-medium text-stone-700">Click on an urban area</p>
                        <p className="text-[10px] text-stone-400">
                          Metro areas are highlighted on the map
                        </p>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="space-y-3">
                    <div className="p-2.5 bg-indigo-50 rounded-md border border-indigo-200">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-indigo-600" />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-indigo-800 truncate">
                            {selectedUrbanArea.name}
                          </p>
                          <p className="text-[10px] text-indigo-600">Metro Area Selected</p>
                        </div>
                        <button
                          onClick={() => onUrbanAreaSelect?.(null)}
                          className="p-1 hover:bg-indigo-100 rounded transition-colors"
                        >
                          <X className="h-3 w-3 text-indigo-500" />
                        </button>
                      </div>
                    </div>
                    <button
                      onClick={handleUrbanContinue}
                      className="w-full py-2.5 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 transition-colors flex items-center justify-center gap-2"
                    >
                      Continue <ArrowRight className="h-4 w-4" />
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Step 2: ZIP Selection */}
            {step === 'zip' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-semibold text-stone-500 uppercase tracking-wider">
                    Step 2: Select ZIP Code
                  </p>
                  <button onClick={handleBack} className="text-[10px] text-stone-400 hover:text-stone-600">
                    ← Back
                  </button>
                </div>

                {/* Urban area context */}
                <div className="p-2 bg-indigo-50/50 rounded-md border border-indigo-100 flex items-center gap-2">
                  <MapPin className="h-3.5 w-3.5 text-indigo-500" />
                  <span className="text-xs text-indigo-700 truncate">{selectedUrbanArea?.name}</span>
                </div>

                {!selectedZip ? (
                  <div className="p-3 bg-stone-50 rounded-md border border-stone-200">
                    <div className="flex flex-col items-center gap-2 text-center">
                      <Hash className="h-8 w-8 text-emerald-500" />
                      <p className="text-xs font-medium text-stone-700">Click on a ZIP code</p>
                      <p className="text-[10px] text-stone-400">
                        ZIP boundaries are shown within the metro area
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="p-2.5 bg-emerald-50 rounded-md border border-emerald-200">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-emerald-800">
                            ZIP {selectedZip.code}
                          </p>
                          <p className="text-[10px] text-emerald-600">Selected</p>
                        </div>
                        <button
                          onClick={() => onZipSelect?.(null)}
                          className="p-1 hover:bg-emerald-100 rounded transition-colors"
                        >
                          <X className="h-3 w-3 text-emerald-600" />
                        </button>
                      </div>
                    </div>
                    <button
                      onClick={handleZipContinue}
                      className="w-full py-2.5 bg-emerald-600 text-white rounded-md text-sm font-medium hover:bg-emerald-700 transition-colors flex items-center justify-center gap-2"
                    >
                      Continue <ArrowRight className="h-4 w-4" />
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Step 3: Area Choice */}
            {step === 'area_choice' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-semibold text-stone-500 uppercase tracking-wider">
                    Step 3: Search Area
                  </p>
                  <button onClick={handleBack} className="text-[10px] text-stone-400 hover:text-stone-600">
                    ← Back
                  </button>
                </div>

                {/* Context */}
                <div className="p-2 bg-emerald-50/50 rounded-md border border-emerald-100 flex items-center gap-2">
                  <Hash className="h-3.5 w-3.5 text-emerald-500" />
                  <span className="text-xs text-emerald-700">ZIP {selectedZip?.code}</span>
                </div>

                {!areaChoice && (
                  <div className="space-y-2">
                    <button
                      onClick={() => handleAreaChoice('entire_zip')}
                      className="w-full p-3 bg-white border border-stone-200 rounded-md hover:bg-stone-50 transition-colors text-left"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
                          <Hash className="h-5 w-5 text-emerald-600" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-stone-800">Search Entire ZIP</p>
                          <p className="text-xs text-stone-500">Find all matching properties in {selectedZip?.code}</p>
                        </div>
                      </div>
                    </button>

                    <button
                      onClick={() => handleAreaChoice('draw')}
                      className="w-full p-3 bg-white border border-stone-200 rounded-md hover:bg-stone-50 transition-colors text-left"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                          <Hexagon className="h-5 w-5 text-blue-600" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-stone-800">Draw Custom Area</p>
                          <p className="text-xs text-stone-500">Draw a specific area within the ZIP</p>
                        </div>
                      </div>
                    </button>
                  </div>
                )}

                {areaChoice === 'draw' && !drawnPolygon && (
                  <div className="space-y-2">
                    <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
                      <div className="flex items-center gap-2">
                        <Hexagon className="h-4 w-4 text-blue-600 animate-pulse" />
                        <span className="text-xs font-medium text-blue-700">
                          {isDrawing ? 'Drawing... Click points, double-click to finish' : 'Starting drawing mode...'}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        setAreaChoice(null)
                        onCancelDrawing?.()
                      }}
                      className="w-full py-2 text-xs text-stone-500 hover:text-stone-700"
                    >
                      Cancel
                    </button>
                  </div>
                )}

                {drawnPolygon && areaChoice === 'draw' && (
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-blue-600" />
                      <span className="text-xs font-medium text-blue-700">Area drawn!</span>
                      <button
                        onClick={() => {
                          onClearDrawnPolygon?.()
                          setAreaChoice(null)
                        }}
                        className="ml-auto p-1 hover:bg-blue-100 rounded"
                      >
                        <X className="h-3 w-3 text-blue-600" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Step 4: Property Type */}
            {step === 'property_type' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-semibold text-stone-500 uppercase tracking-wider">
                    Step 4: Property Type
                  </p>
                  <button onClick={handleBack} className="text-[10px] text-stone-400 hover:text-stone-600">
                    ← Back
                  </button>
                </div>

                {/* Context */}
                <div className="p-2 bg-stone-50 rounded-md border border-stone-200 flex items-center gap-2">
                  {areaChoice === 'draw' ? (
                    <>
                      <Hexagon className="h-3.5 w-3.5 text-blue-500" />
                      <span className="text-xs text-stone-600">Custom drawn area</span>
                    </>
                  ) : (
                    <>
                      <Hash className="h-3.5 w-3.5 text-emerald-500" />
                      <span className="text-xs text-stone-600">Entire ZIP {selectedZip?.code}</span>
                    </>
                  )}
                </div>

                {/* Property type input */}
                <div className="space-y-2">
                  <label className="text-xs text-stone-600">
                    What type of property are you looking for?
                  </label>
                  <input
                    type="text"
                    value={propertyType}
                    onChange={(e) => setPropertyType(e.target.value)}
                    placeholder="e.g., big restaurants, auto repair shops, hotels..."
                    className="w-full px-3 py-2.5 bg-stone-50 border border-stone-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && propertyType.trim()) {
                        handleSearch()
                      }
                    }}
                  />
                  <p className="text-[10px] text-stone-400">
                    Describe in natural language. We&apos;ll find matching businesses and their parcels.
                  </p>
                </div>

                {/* Quick suggestions */}
                <div className="flex flex-wrap gap-1.5">
                  {['Restaurants', 'Hotels', 'Gas Stations', 'Shopping Centers', 'Auto Repair'].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => setPropertyType(suggestion.toLowerCase())}
                      className="px-2 py-1 text-[10px] bg-stone-100 text-stone-600 rounded hover:bg-stone-200 transition-colors"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>

                {/* Search button */}
                <button
                  onClick={handleSearch}
                  disabled={!propertyType.trim()}
                  className={cn(
                    "w-full py-2.5 rounded-md text-sm font-medium flex items-center justify-center gap-2 transition-colors",
                    propertyType.trim()
                      ? "bg-emerald-600 text-white hover:bg-emerald-700"
                      : "bg-stone-200 text-stone-400 cursor-not-allowed"
                  )}
                >
                  <Search className="h-4 w-4" />
                  Search Properties
                </button>
              </div>
            )}

            {/* Step 5: Results */}
            {step === 'results' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-semibold text-stone-500 uppercase tracking-wider">
                    Results
                  </p>
                  <button onClick={handleBack} className="text-[10px] text-stone-400 hover:text-stone-600">
                    ← Back
                  </button>
                </div>

                {/* Search context */}
                <div className="p-2 bg-stone-50 rounded-md border border-stone-200">
                  <p className="text-xs text-stone-600 truncate">
                    &quot;{propertyType}&quot; in {areaChoice === 'entire_zip' ? `ZIP ${selectedZip?.code}` : 'drawn area'}
                  </p>
                </div>

                {/* Loading state */}
                {isDiscovering && (
                  <div className="py-8 flex flex-col items-center gap-2">
                    <Loader2 className="h-8 w-8 text-stone-400 animate-spin" />
                    <p className="text-xs text-stone-500">Searching businesses...</p>
                    <p className="text-[10px] text-stone-400">Finding places and matching parcels</p>
                  </div>
                )}

                {/* Results list */}
                {!isDiscovering && discoveredPlaces.length > 0 && (
                  <>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-stone-600">
                        {discoveredPlaces.length} propert{discoveredPlaces.length !== 1 ? 'ies' : 'y'} found
                      </span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={onSelectAll}
                          className="text-[10px] text-emerald-600 hover:text-emerald-700"
                        >
                          Select All
                        </button>
                        <span className="text-stone-300">|</span>
                        <button
                          onClick={onDeselectAll}
                          className="text-[10px] text-stone-400 hover:text-stone-600"
                        >
                          Clear
                        </button>
                      </div>
                    </div>

                    <div className="max-h-64 overflow-y-auto space-y-1.5 border border-stone-100 rounded-md p-1.5">
                      {discoveredPlaces.map((place) => {
                        const isSelected = selectedPlaces.some(p => p.place_id === place.place_id)
                        return (
                          <PlaceItem
                            key={place.place_id}
                            place={place}
                            isSelected={isSelected}
                            onClick={() => onPlaceSelect(place, !isSelected)}
                          />
                        )
                      })}
                    </div>

                    {/* Processing progress */}
                    {isProcessing && processingProgress && (
                      <div className="p-3 bg-blue-50 border border-blue-200 rounded-md space-y-2">
                        <div className="flex items-center gap-2">
                          <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />
                          <span className="text-xs font-medium text-blue-700">
                            Processing...
                          </span>
                        </div>
                        <p className="text-xs text-blue-600">{processingProgress.message}</p>
                        {processingProgress.current && processingProgress.total && (
                          <div className="space-y-1">
                            <div className="h-1.5 bg-blue-100 rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-blue-600 transition-all duration-300"
                                style={{ width: `${(processingProgress.current / processingProgress.total) * 100}%` }}
                              />
                            </div>
                            <p className="text-[10px] text-blue-500 text-center">
                              {processingProgress.current} / {processingProgress.total}
                            </p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Processed results */}
                    {!isProcessing && processedResults.length > 0 && (
                      <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-md space-y-2">
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                          <span className="text-xs font-medium text-emerald-700">
                            Processing Complete
                          </span>
                        </div>
                        <div className="text-xs text-emerald-600 space-y-1">
                          <p>✓ {processedResults.length} places processed</p>
                          <p>✓ {processedResults.filter(r => r.contact).length} contacts found</p>
                        </div>
                        <div className="max-h-32 overflow-y-auto space-y-1 mt-2">
                          {processedResults.filter(r => r.contact).map((result) => (
                            <div key={result.place_id} className="p-2 bg-white rounded border border-emerald-100 text-xs">
                              <p className="font-medium text-stone-700 truncate">{result.name}</p>
                              {result.contact?.phone && (
                                <p className="text-emerald-600 flex items-center gap-1">
                                  <Phone className="h-3 w-3" /> {result.contact.phone}
                                </p>
                              )}
                              {result.contact?.email && (
                                <p className="text-emerald-600 truncate">{result.contact.email}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Selection summary & process button */}
                    {!isProcessing && processedResults.length === 0 && (
                      <div className="pt-2 border-t border-stone-100 space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-stone-600">
                            {selectedPlaces.length} selected
                          </span>
                          <span className="text-stone-400">
                            {selectedPlaces.filter(p => p.parcel_id).length} with parcels
                          </span>
                        </div>
                        <button
                          onClick={handleProcess}
                          disabled={selectedPlaces.length === 0}
                          className={cn(
                            "w-full py-2.5 rounded-md text-sm font-medium flex items-center justify-center gap-2 transition-colors",
                            selectedPlaces.length > 0
                              ? "bg-emerald-600 text-white hover:bg-emerald-700"
                              : "bg-stone-200 text-stone-400 cursor-not-allowed"
                          )}
                        >
                          <ArrowRight className="h-4 w-4" />
                          Process Selected ({selectedPlaces.length})
                        </button>
                      </div>
                    )}
                  </>
                )}

                {/* No results */}
                {!isDiscovering && discoveredPlaces.length === 0 && (
                  <div className="py-6 text-center">
                    <Building2 className="h-8 w-8 text-stone-300 mx-auto mb-2" />
                    <p className="text-xs text-stone-500">
                      No properties found
                    </p>
                    <p className="text-[10px] text-stone-400 mt-1">
                      Try a different search term or area
                    </p>
                    <button
                      onClick={handleBack}
                      className="mt-3 text-xs text-emerald-600 hover:text-emerald-700"
                    >
                      Modify Search
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Clear button - visible when not on first step */}
            {step !== 'urban' && (
              <div className="pt-3 mt-3 border-t border-stone-100">
                <button
                  onClick={handleClear}
                  className="w-full py-2 text-xs text-stone-400 hover:text-stone-600 transition-colors"
                >
                  Clear & Start Over
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// Place item component
function PlaceItem({
  place,
  isSelected,
  onClick,
}: {
  place: PlaceWithParcel
  isSelected: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full p-2.5 rounded-md text-left transition-colors flex items-start gap-2",
        isSelected
          ? "bg-emerald-50 border border-emerald-200"
          : "bg-white border border-stone-100 hover:bg-stone-50"
      )}
    >
      {isSelected ? (
        <SquareCheck className="h-4 w-4 text-emerald-600 flex-shrink-0 mt-0.5" />
      ) : (
        <Square className="h-4 w-4 text-stone-300 flex-shrink-0 mt-0.5" />
      )}
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-stone-700 truncate">
          {place.name}
        </p>
        <p className="text-[10px] text-stone-500 truncate">
          {place.address}
        </p>
        <div className="flex items-center gap-2 mt-1">
          {place.rating && (
            <span className="flex items-center gap-0.5 text-[10px] text-amber-600">
              <Star className="h-3 w-3" />
              {place.rating.toFixed(1)}
            </span>
          )}
          {place.parcel_acreage && (
            <span className="text-[10px] text-stone-400">
              {place.parcel_acreage.toFixed(2)} ac
            </span>
          )}
          {place.phone && (
            <Phone className="h-3 w-3 text-stone-400" />
          )}
          {place.website && (
            <Globe className="h-3 w-3 text-stone-400" />
          )}
          {!place.parcel_id && (
            <span className="text-[10px] text-orange-500">No parcel</span>
          )}
        </div>
      </div>
    </button>
  )
}

export default DiscoveryPanel
