export default function Header({ sidebarOpen, onToggleSidebar }) {
  return (
    <header className="site-header">
      <div className="header-title">
        <button
          type="button"
          className="sidebar-toggle"
          aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
          aria-expanded={sidebarOpen}
          onClick={onToggleSidebar}
        >
          <span className="sidebar-toggle-bar" />
          <span className="sidebar-toggle-bar" />
          <span className="sidebar-toggle-bar" />
        </button>
        <span className="header-logo" aria-hidden="true">⚗️</span>
        <span>Acme Discovery</span>
      </div>
      <div className="header-meta">Sortilin inhibitor screen</div>
    </header>
  );
}
