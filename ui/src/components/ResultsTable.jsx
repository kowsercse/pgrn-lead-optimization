import MoleculeImage from "./MoleculeImage.jsx";

const RUNS = [
  {
    id: "MOL-2847",
    smiles: "CC(C)Cc1ccc(cc1)C(C)C(O)=O",
    affinity: 2.3,
    activity: "Very High",
    badge: "badge-high",
  },
  {
    id: "MOL-2856",
    smiles: "O=C(O)Cc1ccccc1NC(=O)c2ccccc2",
    affinity: 5.7,
    activity: "High",
    badge: "badge-high",
  },
  {
    id: "MOL-2891",
    smiles: "CC(C)CC(NC(=O)c1ccc(cc1)N)C(=O)O",
    affinity: 12.4,
    activity: "Moderate",
    badge: "badge-medium",
  },
  {
    id: "MOL-2915",
    smiles: "O=C(Nc1ccc(cc1)S(=O)(=O)N)c2cccnc2",
    affinity: 8.1,
    activity: "High",
    badge: "badge-high",
  },
  {
    id: "MOL-2934",
    smiles: "CC(=O)Nc1ccc(cc1)O",
    affinity: 34.2,
    activity: "Low",
    badge: "badge-low",
  },
];

export default function ResultsTable() {
  return (
    <div className="results-table">
      <h2>Molecular Optimization Runs</h2>
      <table>
        <thead>
          <tr>
            <th>Molecule ID</th>
            <th>Structure</th>
            <th>Binding Affinity (nM)</th>
            <th>Predicted Activity</th>
          </tr>
        </thead>
        <tbody>
          {RUNS.map((run) => (
            <tr
              key={run.id}
              className="results-table-row"
              tabIndex={0}
              role="link"
              onClick={() => {
                window.location.href = "#";
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  window.location.href = "#";
                }
              }}
            >
              <td>{run.id}</td>
              <td>
                <MoleculeImage smiles={run.smiles} />
              </td>
              <td>{run.affinity}</td>
              <td>
                <span className={`badge ${run.badge}`}>{run.activity}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
