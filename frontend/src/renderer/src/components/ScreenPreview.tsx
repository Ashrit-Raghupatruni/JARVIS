import React, { useState } from 'react'
import { useAppStore } from '../stores/appStore'

const ScreenPreview: React.FC = () => {
  const screenPreview = useAppStore((s) => s.screenPreview)
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <>
      {/* Thumbnail */}
      <div
        className="glass rounded-xl overflow-hidden cursor-pointer transition-all duration-300 hover:border-jarvis-border-bright group"
        style={{
          width: 180,
          height: 110,
          boxShadow: '0 0 20px rgba(0, 0, 0, 0.3)'
        }}
        onClick={() => screenPreview && setIsExpanded(true)}
      >
        {screenPreview ? (
          <div className="relative w-full h-full">
            <img
              src={screenPreview}
              alt="Screen capture"
              className="w-full h-full object-cover"
            />
            {/* Overlay on hover */}
            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center">
              <svg
                className="w-6 h-6 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7"
                />
              </svg>
            </div>

            {/* Label */}
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent px-2 py-1">
              <span className="text-[9px] text-white/80 uppercase tracking-wider font-medium">
                Screen Preview
              </span>
            </div>
          </div>
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center gap-2">
            <svg
              className="w-8 h-8 text-jarvis-text-muted/30"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1}
            >
              <path
                strokeLinecap="round"
                d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
              />
            </svg>
            <span className="text-[9px] text-jarvis-text-muted/40 uppercase tracking-wider">
              No Preview
            </span>
          </div>
        )}
      </div>

      {/* Expanded Modal */}
      {isExpanded && screenPreview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm animate-fade-in"
          onClick={() => setIsExpanded(false)}
        >
          <div
            className="relative max-w-[90vw] max-h-[85vh] glass-heavy rounded-xl overflow-hidden animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close button */}
            <button
              className="absolute top-3 right-3 z-10 w-8 h-8 flex items-center justify-center rounded-full bg-black/50 hover:bg-black/70 transition-fast"
              onClick={() => setIsExpanded(false)}
            >
              <svg
                className="w-4 h-4 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            <img
              src={screenPreview}
              alt="Screen capture (full size)"
              className="max-w-full max-h-[85vh] object-contain"
            />
          </div>
        </div>
      )}
    </>
  )
}

export default ScreenPreview
