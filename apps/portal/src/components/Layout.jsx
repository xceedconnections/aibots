import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { clearToken } from '../api'

export default function Layout() {
  const nav = useNavigate()
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">AI</span>
          <div>
            <strong>AIBOTS</strong>
            <small>VICIdial Voice</small>
          </div>
        </div>
        <nav>
          <NavLink end to="/">Dashboard</NavLink>
          <NavLink to="/bots">Bots</NavLink>
          <NavLink to="/carrier">SIP Carrier</NavLink>
          <NavLink to="/calls">Calls</NavLink>
        </nav>
        <button
          className="btn ghost logout"
          onClick={() => {
            clearToken()
            nav('/login')
          }}
        >
          Sign out
        </button>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
