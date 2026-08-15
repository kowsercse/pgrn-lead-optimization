export default function ToolStatus() {
  return (
    <div className="tool-status">
      <span className="tool-status-icon" aria-hidden="true">🧬</span>
      <div className="tool-status-body">
        <p className="tool-status-title">Running molecular discovery tool</p>
        <p className="tool-status-desc">
          Screened 5 candidate ligands against the Sortilin binding pocket,
          scored predicted binding affinity, and started optimization on the
          top hits.
        </p>
        <a
          className="tool-status-link"
          href="https://en.wikipedia.org/wiki/Molecular_docking"
          target="_blank"
          rel="noopener"
        >
          What does this tool do? ↗
        </a>
      </div>
    </div>
  );
}
