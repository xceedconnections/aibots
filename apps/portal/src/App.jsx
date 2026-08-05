import { Navigate, Route, Routes } from 'react-router-dom'
import { isLoggedIn } from './api'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Bots from './pages/Bots'
import BotEditor from './pages/BotEditor'
import Carrier from './pages/Carrier'
import Calls from './pages/Calls'
import Campaigns from './pages/Campaigns'
import Vicidialers from './pages/Vicidialers'
import Settings from './pages/Settings'

function Private({ children }) {
  if (!isLoggedIn()) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Private>
            <Layout />
          </Private>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="campaigns" element={<Campaigns />} />
        <Route path="bots" element={<Bots />} />
        <Route path="bots/:id" element={<BotEditor />} />
        <Route path="vicidialers" element={<Vicidialers />} />
        <Route path="carrier" element={<Carrier />} />
        <Route path="calls" element={<Calls />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
