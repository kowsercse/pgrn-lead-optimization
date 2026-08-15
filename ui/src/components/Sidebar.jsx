import { useCallback, useEffect, useRef } from "react";

const CHATS = [
  { title: "Sortilin blocker screen", meta: "Today", active: true },
  { title: "GLP-1 analog stability", meta: "Yesterday" },
  { title: "Kinase selectivity panel", meta: "3 days ago" },
];

const MIN_WIDTH = 180;
const MAX_WIDTH = 420;

export default function Sidebar({ width, onWidthChange, open, onClose }) {
  const draggingRef = useRef(false);

  const handleResizeStart = useCallback((event) => {
    event.preventDefault();
    draggingRef.current = true;
    document.body.classList.add("sidebar-resizing");
  }, []);

  useEffect(() => {
    function handlePointerMove(event) {
      if (!draggingRef.current) return;
      const next = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, event.clientX));
      onWidthChange(next);
    }
    function handlePointerUp() {
      draggingRef.current = false;
      document.body.classList.remove("sidebar-resizing");
    }
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [onWidthChange]);

  return (
    <>
      {open && (
        <div
          className="sidebar-backdrop"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={open ? "sidebar sidebar-open" : "sidebar"}
        style={{ "--sidebar-width": `${width}px` }}
      >
        <button type="button" className="btn btn-primary sidebar-new-chat">
          + New chat
        </button>
        <nav className="chat-list">
          {CHATS.map((chat) => (
            <a
              key={chat.title}
              className={
                chat.active
                  ? "chat-list-item chat-list-item-active"
                  : "chat-list-item"
              }
              href="#"
            >
              <span className="chat-list-title">{chat.title}</span>
              <span className="chat-list-meta">{chat.meta}</span>
            </a>
          ))}
        </nav>
        <div
          className="sidebar-resize-handle"
          onPointerDown={handleResizeStart}
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize sidebar"
        />
      </aside>
    </>
  );
}
