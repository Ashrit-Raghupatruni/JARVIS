import React from 'react'
import { ExternalLink, Search, Tag, Globe, ShoppingBag, Layers, Zap } from 'lucide-react'

export interface SearchResultCard {
  title: string
  url: string
  snippet: string
  source?: string
  image_url?: string
  price?: string
  rating?: string
  category?: 'general' | 'price' | 'compare' | 'news_parallel'
}

interface DynamicContentPanelProps {
  query?: string
  mode?: 'general' | 'price' | 'compare' | 'news_parallel'
  executionTime?: number
  results?: SearchResultCard[]
  isLoading?: boolean
}

export const DynamicContentPanel: React.FC<DynamicContentPanelProps> = ({
  query,
  mode = 'general',
  executionTime,
  results = [],
  isLoading = false,
}) => {
  if (!query && results.length === 0 && !isLoading) {
    return null
  }

  return (
    <div className="w-full bg-slate-900/80 backdrop-blur-md border border-cyan-500/20 rounded-xl p-4 my-3 shadow-[0_4px_20px_rgba(0,0,0,0.4)]">
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
        <div className="flex items-center space-x-2">
          {mode === 'price' ? (
            <ShoppingBag className="w-5 h-5 text-cyan-400" />
          ) : mode === 'compare' ? (
            <Layers className="w-5 h-5 text-cyan-400" />
          ) : mode === 'news_parallel' ? (
            <Zap className="w-5 h-5 text-amber-400 animate-pulse" />
          ) : (
            <Search className="w-5 h-5 text-cyan-400" />
          )}
          <span className="text-sm font-semibold text-slate-200">
            {mode === 'price'
              ? 'Price Comparison Results'
              : mode === 'compare'
              ? 'Feature Matrix Comparison'
              : mode === 'news_parallel'
              ? '⚡ Parallel Concurrent News Engine'
              : 'Search Insights & Visual Cards'}
          </span>
          {query && (
            <span className="text-xs px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-500/30 text-cyan-300 font-mono">
              "{query}"
            </span>
          )}
        </div>

        <div className="flex items-center space-x-2">
          {executionTime !== undefined && (
            <span className="text-[11px] px-2 py-0.5 rounded bg-amber-950/60 border border-amber-500/40 text-amber-300 font-mono">
              ⚡ {executionTime}s
            </span>
          )}
          <span className="text-xs text-slate-400 font-mono">
            {results.length} result(s)
          </span>
        </div>
      </div>

      {/* Loading Skeleton */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 animate-pulse">
          {[1, 2, 3, 4].map((idx) => (
            <div key={idx} className="h-24 bg-slate-800/60 rounded-lg border border-slate-800"></div>
          ))}
        </div>
      ) : results.length === 0 ? (
        <div className="text-center py-6 text-slate-400 text-sm">
          No visual search cards available for this query.
        </div>
      ) : (
        /* Results Grid */
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[380px] overflow-y-auto pr-1">
          {results.map((res, idx) => (
            <a
              key={idx}
              href={res.url}
              target="_blank"
              rel="noreferrer"
              className="group flex flex-col justify-between bg-slate-950/60 hover:bg-slate-800/80 border border-slate-800 hover:border-cyan-500/40 rounded-lg p-3 transition-all duration-200"
            >
              <div>
                <div className="flex items-start justify-between gap-2">
                  <h4 className="text-sm font-medium text-slate-100 group-hover:text-cyan-300 transition-colors line-clamp-1">
                    {res.title}
                  </h4>
                  <ExternalLink className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-400 flex-shrink-0" />
                </div>

                <p className="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                  {res.snippet}
                </p>
              </div>

              <div className="flex items-center justify-between mt-3 pt-2 border-t border-slate-800/60 text-xs">
                <div className="flex items-center space-x-1.5 text-slate-400 font-mono">
                  <Globe className="w-3 h-3 text-cyan-400" />
                  <span>{res.source || 'Web'}</span>
                </div>

                {res.price && (
                  <span className="px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 font-semibold font-mono text-[11px]">
                    {res.price}
                  </span>
                )}
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
