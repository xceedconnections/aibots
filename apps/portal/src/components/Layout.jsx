import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { clearToken } from '../api'

const TITLES = {
  '/': 'Dashboard',
  '/campaigns': 'Campaigns',
  '/bots': 'Bots / Scripts',
  '/vicidialers': 'VICIdial Servers',
  '/carrier': 'SIP Carrier',
  '/calls': 'Calls',
  '/settings': 'Settings',
}

export default function Layout() {
  const nav = useNavigate()
  const loc = useLocation()
  const title =
    TITLES[loc.pathname] ||
    (loc.pathname.startsWith('/bots/') ? 'Bot editor' : 'AIBOTS')

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark">AI</span>
          <div>
            <span>AIBOTS</span>
            <small>VICIdial Voice Agents</small>
          </div>
        </div>

        <div className="sidebar-section">Operations</div>
        <nav>
          <NavLink end to="/"><span className="nav-ico">▣</span>Dashboard</NavLink>
          <NavLink to="/campaigns"><span className="nav-ico">▤</span>Campaigns</NavLink>
          <NavLink to="/bots"><span className="nav-ico">◎</span>Bots / Scripts</NavLink>
          <NavLink to="/calls"><span className="nav-ico">☎</span>Calls</NavLink>
        </nav>

        <div className="sidebar-section">Telephony</div>
        <nav>
          <NavLink to="/vicidialers"><span className="nav-ico">◈</span>VICIdial Servers</NavLink>
          <NavLink to="/carrier"><span className="nav-ico">⇄</span>SIP Carrier</NavLink>
        </nav>

        <div className="sidebar-section">System</div>
        <nav>
          <NavLink to="/settings"><span className="nav-ico">⚙</span>Settings</NavLink>
        </nav>

        <button
          className="logout"
          type="button"
          onClick={() => {
            clearToken()
            nav('/login')
          }}
        >
          Sign out
        </button>
      </aside>

      <div className="content-wrap">
        <header className="topbar">
          <h2>{title}</h2>
          <div className="topbar-meta">
            <span className="pill ok">SYSTEM ONLINE</span>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
