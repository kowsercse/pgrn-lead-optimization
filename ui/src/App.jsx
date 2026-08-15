import { useState } from "react";
import "./App.css";
import Header from "./components/Header.jsx";
import Sidebar from "./components/Sidebar.jsx";
import ChatThread from "./components/ChatThread.jsx";
import ResultsTable from "./components/ResultsTable.jsx";
import Composer from "./components/Composer.jsx";

const DEFAULT_SIDEBAR_WIDTH = 240;

export default function App() {
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_SIDEBAR_WIDTH);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="app-shell">
      <Header
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((open) => !open)}
      />
      <div className="app-body">
        <Sidebar
          width={sidebarWidth}
          onWidthChange={setSidebarWidth}
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />
        <main className="content">
          <div className="scroll-area">
            <ChatThread />
            <ResultsTable />
          </div>
          <Composer />
        </main>
      </div>
    </div>
  );
}
