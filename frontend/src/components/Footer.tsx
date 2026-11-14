import { useState, useEffect } from 'react'
import { ChevronDown, Info, Shield, X, ExternalLink } from 'lucide-react'

interface FooterProps {
  variant?: 'landing' | 'global' | 'india'
  className?: string
}

export default function Footer({ variant = 'landing', className = '' }: FooterProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)

  // Close modal on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsModalOpen(false)
      }
    }
    if (isModalOpen) {
      window.addEventListener('keydown', handleKeyDown)
    }
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isModalOpen])

  // Contextual border and background accents based on route variant
  const borderClass =
    variant === 'india'
      ? 'border-[#1f2836]'
      : variant === 'global'
      ? 'border-[#1b2533]'
      : 'border-[#16212e]'

  return (
    <>
      <footer
        className={`amquant-institutional-footer border-t ${borderClass} bg-[#06090e]/95 py-5 px-4 sm:px-6 lg:px-8 text-xs text-[#94a3b8] transition-all ${className}`}
        role="contentinfo"
        aria-label="Platform Copyright and Legal Notice"
      >
        <div className="max-w-7xl mx-auto">
          {/* Compact Primary Bar */}
          <div className="flex flex-col md:flex-row items-center justify-between gap-3 text-center md:text-left">
            {/* Copyright & Platform Designation */}
            <div className="flex flex-wrap items-center justify-center md:justify-start gap-x-2.5 gap-y-1 text-xs">
              <span className="font-semibold text-[#f1f5f9] tracking-wide">
                © 2026 Aditya M.
              </span>
              <span className="text-[#475569] hidden sm:inline">•</span>
              <span className="text-[#cbd5e1] font-medium">All Rights Reserved.</span>
              <span className="text-[#475569] hidden md:inline">•</span>
              <span className="text-[#64748b] hidden md:inline">
                AMQUANT – Quantitative Finance Research & Analytics
              </span>
            </div>

            {/* Subtle Interactive Triggers */}
            <div className="flex items-center gap-2 sm:gap-3 text-[11px]">
              <button
                type="button"
                onClick={() => setIsExpanded(prev => !prev)}
                className="px-2.5 py-1 rounded bg-[#0e1622] hover:bg-[#15202e] border border-[#1e2a3a] text-[#94a3b8] hover:text-[#f8fafc] font-medium transition-all flex items-center gap-1.5 focus:outline-none focus:ring-1 focus:ring-[#38bdf8]/40"
                aria-expanded={isExpanded}
                aria-controls="amquant-legal-expanded-notice"
              >
                <span>Legal Notice & Disclaimer</span>
                <ChevronDown
                  size={12}
                  className={`transition-transform duration-200 text-[#64748b] ${isExpanded ? 'rotate-180 text-[#38bdf8]' : ''}`}
                />
              </button>

              <button
                type="button"
                onClick={() => setIsModalOpen(true)}
                className="px-2.5 py-1 rounded bg-[#0e1622] hover:bg-[#15202e] border border-[#1e2a3a] text-[#64748b] hover:text-[#cbd5e1] transition-all flex items-center gap-1 focus:outline-none"
                title="View Full Intellectual Property Statement in Dialog"
              >
                <Shield size={11} className="text-[#38bdf8]" />
                <span className="hidden sm:inline">IP & Disclaimer</span>
              </button>
            </div>
          </div>

          {/* Expandable Section */}
          {isExpanded && (
            <div
              id="amquant-legal-expanded-notice"
              className="mt-4 pt-4 border-t border-[#172230] text-[11px] leading-relaxed text-[#94a3b8] space-y-3 bg-[#080d14] p-4 rounded-lg border border-[#16212e] animate-in fade-in duration-200"
            >
              <div className="flex items-center justify-between pb-2 border-b border-[#141d28]">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded bg-[#101b29] border border-[#1d2d42] flex items-center justify-center text-[#38bdf8]">
                    <Shield size={11} />
                  </div>
                  <span className="font-semibold text-xs text-[#f1f5f9] tracking-wide">
                    AMQUANT Intellectual Property Notice & Legal Disclaimer
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(true)}
                    className="text-[10px] text-[#38bdf8] hover:text-[#7dd3fc] hover:underline flex items-center gap-1"
                  >
                    <span>Open in Dialog</span>
                    <ExternalLink size={10} />
                  </button>
                  <span className="text-[#253243]">•</span>
                  <button
                    type="button"
                    onClick={() => setIsExpanded(false)}
                    className="text-[10px] text-[#64748b] hover:text-[#94a3b8] hover:underline"
                  >
                    Collapse
                  </button>
                </div>
              </div>

              {/* Exact Required Copyright Statement */}
              <div className="space-y-2 text-[#cbd5e1]">
                <p className="font-medium text-[#f8fafc]">
                  © 2026 Aditya M. All Rights Reserved.
                </p>

                <p>
                  AMQUANT is an independently developed quantitative finance research and analytics platform. Its original software, source code, design, branding, documentation and proprietary materials are the intellectual property of Aditya M, except for third-party components and materials belonging to their respective owners.
                </p>

                <p>
                  Unauthorised copying, reproduction, modification, redistribution or commercial use without prior written permission is prohibited.
                </p>
              </div>

              {/* Disclaimer Box */}
              <div className="p-3 rounded bg-[#0b1017] border border-[#1c2635] text-[#94a3b8] text-[11px] leading-relaxed">
                <span className="font-semibold text-[#fb923c]">Disclaimer: </span>
                AMQUANT is intended for educational, research and analytical purposes only. Backtesting results and simulations do not guarantee future performance. Nothing on this platform constitutes financial or investment advice.
              </div>
            </div>
          )}
        </div>
      </footer>

      {/* Dedicated Legal / About Modal */}
      {isModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={() => setIsModalOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="legal-modal-title"
        >
          <div
            className="w-full max-w-2xl bg-[#090d14] border border-[#1e2a3a] rounded-xl shadow-2xl p-6 sm:p-7 relative text-[#e2e8f0] font-sans"
            onClick={e => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-start justify-between pb-4 border-b border-[#182332]">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-[#0e1724] border border-[#1d2d42] flex items-center justify-center text-[#38bdf8] shadow-sm">
                  <Shield size={20} />
                </div>
                <div>
                  <h2 id="legal-modal-title" className="text-base sm:text-lg font-bold text-[#f8fafc]">
                    Intellectual Property Notice & Disclaimer
                  </h2>
                  <p className="text-xs text-[#64748b]">
                    AMQUANT – Quantitative Finance Research & Analytics
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="w-8 h-8 rounded-lg bg-[#0e1622] hover:bg-[#162232] border border-[#1e2a3a] text-[#94a3b8] hover:text-[#f8fafc] flex items-center justify-center transition-colors"
                aria-label="Close legal notice"
              >
                <X size={16} />
              </button>
            </div>

            {/* Modal Body with Exact Required Wording */}
            <div className="py-5 space-y-4 text-xs sm:text-sm text-[#cbd5e1] leading-relaxed max-h-[65vh] overflow-y-auto pr-1">
              <div className="p-3.5 rounded-lg bg-[#0c131d] border border-[#1c293b]">
                <p className="font-semibold text-sm sm:text-base text-[#f8fafc]">
                  © 2026 Aditya M. All Rights Reserved.
                </p>
              </div>

              <p>
                AMQUANT is an independently developed quantitative finance research and analytics platform. Its original software, source code, design, branding, documentation and proprietary materials are the intellectual property of Aditya M, except for third-party components and materials belonging to their respective owners.
              </p>

              <p>
                Unauthorised copying, reproduction, modification, redistribution or commercial use without prior written permission is prohibited.
              </p>

              <div className="p-4 rounded-lg bg-[#14120f] border border-[#3b2b1a] text-[#fbbf24] space-y-1.5">
                <div className="flex items-center gap-2 font-semibold text-xs sm:text-sm text-[#f59e0b]">
                  <Info size={15} />
                  <span>Important Legal Disclaimer</span>
                </div>
                <p className="text-xs text-[#fde68a] leading-relaxed">
                  Disclaimer: AMQUANT is intended for educational, research and analytical purposes only. Backtesting results and simulations do not guarantee future performance. Nothing on this platform constitutes financial or investment advice.
                </p>
              </div>

              <div className="text-[11px] text-[#64748b] border-t border-[#16212e] pt-3 flex flex-wrap items-center justify-between gap-2">
                <span>Platform Owner: Aditya M.</span>
                <span>Jurisdiction: Personal Quantitative Finance Research</span>
                <span>Release Year: 2026</span>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="pt-4 border-t border-[#182332] flex items-center justify-end">
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="px-4 py-2 rounded-lg bg-[#111a26] hover:bg-[#182535] border border-[#233549] text-xs font-semibold text-[#f1f5f9] transition-all"
              >
                Close Notice
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
