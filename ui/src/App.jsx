import { useRef, useState } from "react";
import "./App.css";
import Header from "./components/Header.jsx";
import Sidebar from "./components/Sidebar.jsx";
import ChatThread from "./components/ChatThread.jsx";
import ResultsTable from "./components/ResultsTable.jsx";
import Composer from "./components/Composer.jsx";
import { startAgent, pollUntilComplete, describeOutput } from "./conductor.js";

const DEFAULT_SIDEBAR_WIDTH = 240;

let nextMessageId = 0;
function newMessage(role, content, status) {
  nextMessageId += 1;
  return { id: nextMessageId, role, content, status };
}

export default function App() {
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_SIDEBAR_WIDTH);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [running, setRunning] = useState(false);
  const abortRef = useRef(null);

  function updateMessage(id, patch) {
    setMessages((prev) => prev.map((message) => (message.id === id ? { ...message, ...patch } : message)));
  }

  async function handleSend(prompt) {
    const userMessage = newMessage("user", prompt);
    const assistantMessage = newMessage("assistant", "Starting agent…", "running");
    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setRunning(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const executionId = await startAgent(prompt);
      updateMessage(assistantMessage.id, { content: `Running (execution ${executionId})…` });

      const workflow = await pollUntilComplete(executionId, {
        signal: controller.signal,
        onTick: (wf) => {
          if (wf.status === "RUNNING") {
            updateMessage(assistantMessage.id, { content: `Running (execution ${executionId})…` });
          }
        },
      });

      const { error, text } = describeOutput(workflow);
      updateMessage(assistantMessage.id, { content: text, status: error ? "error" : "done" });
    } catch (err) {
      updateMessage(assistantMessage.id, { content: `Failed to run agent: ${err.message}`, status: "error" });
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }

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
            <ChatThread messages={messages} />
            <ResultsTable />
          </div>
          <Composer onSend={handleSend} disabled={running} />
        </main>
      </div>
    </div>
  );
}
