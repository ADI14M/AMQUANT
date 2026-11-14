import { useNavigate } from 'react-router-dom'
import { Compass, Globe2, Home, LineChart } from 'lucide-react'
import Footer from '../components/Footer'

export default function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-[#080b11] text-[#e2e8f0] flex flex-col items-center justify-center p-6 text-center font-sans">
      <div className="w-16 h-16 rounded-2xl bg-[#111822] border border-[#1e2a38] flex items-center justify-center text-[#38bdf8] mb-6 shadow-xl">
        <LineChart size={32} />
      </div>

      <div className="text-xs font-mono font-bold tracking-widest text-[#38bdf8] uppercase mb-2">
        404 · ROUTE NOT FOUND
      </div>

      <h1 className="text-3xl sm:text-4xl font-extrabold text-[#f8fafc] mb-3">
        Page Not Located
      </h1>

      <p className="text-sm text-[#94a3b8] max-w-md mx-auto mb-8">
        The requested address does not exist within the AMQUANT terminal. Choose a market workspace below to continue your research.
      </p>

      <div className="flex flex-col sm:flex-row items-center gap-3">
        <button
          onClick={() => navigate('/')}
          className="w-full sm:w-auto px-5 py-2.5 rounded-lg bg-[#111822] hover:bg-[#1a2533] border border-[#223142] text-xs font-semibold text-[#f8fafc] transition-all flex items-center justify-center gap-2"
        >
          <Home size={15} />
          <span>AMQUANT Home</span>
        </button>

        <button
          onClick={() => navigate('/global')}
          className="w-full sm:w-auto px-5 py-2.5 rounded-lg bg-[#0284c7] hover:bg-[#0369a1] text-white text-xs font-semibold shadow-md transition-all flex items-center justify-center gap-2"
        >
          <Globe2 size={15} />
          <span>Global Markets</span>
        </button>

        <button
          onClick={() => navigate('/india')}
          className="w-full sm:w-auto px-5 py-2.5 rounded-lg bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-semibold shadow-md transition-all flex items-center justify-center gap-2"
        >
          <Compass size={15} />
          <span>Indian Markets</span>
        </button>
      </div>

      <Footer variant="landing" className="mt-12 w-full max-w-3xl rounded-xl border border-[#16212e]" />
    </div>
  )
}
