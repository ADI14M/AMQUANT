import { BrowserRouter, Routes, Route } from 'react-router-dom'
import AuthModal from './components/AuthModal'
import { AuthProvider } from './context/AuthContext'
import LandingPage from './pages/LandingPage'
import NotFoundPage from './pages/NotFoundPage'
import GlobalApp from './global/GlobalApp'
import IndiaApp from './india/IndiaApp'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/global" element={<GlobalApp />} />
          <Route path="/global/*" element={<GlobalApp />} />
          <Route path="/india" element={<IndiaApp />} />
          <Route path="/india/*" element={<IndiaApp />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
      <AuthModal />
    </AuthProvider>
  )
}
