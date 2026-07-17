import { Navigate, Route, Routes } from 'react-router-dom'
import { isLoggedIn } from './api'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Bots from './pages/Bots'
import BotEditor from './pages/BotEditor'
import Calls from './pages/Calls'

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
        <Route path="bots" element={<Bots />} />
        <Route path="bots/:id" element={<BotEditor />} />
        <Route path="calls" element={<Calls />} />
      </Route>
    </Routes>
  )
}
