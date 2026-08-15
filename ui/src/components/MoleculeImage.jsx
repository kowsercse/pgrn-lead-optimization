import { useEffect, useRef } from "react";
import SmilesDrawer from "smiles-drawer";

const drawer = new SmilesDrawer.Drawer({ width: 160, height: 100 });

export default function MoleculeImage({ smiles }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    SmilesDrawer.parse(
      smiles,
      (tree) => drawer.draw(tree, canvasRef.current, "light", false),
      (err) => console.error(`Failed to parse SMILES "${smiles}":`, err),
    );
  }, [smiles]);

  return (
    <canvas
      ref={canvasRef}
      width={160}
      height={100}
      className="molecule-canvas"
      role="img"
      aria-label={`2D structure for ${smiles}`}
    />
  );
}
