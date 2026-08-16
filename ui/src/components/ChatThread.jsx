import { AssistantIcon, UserIcon } from "./icons.jsx";
import ToolStatus from "./ToolStatus.jsx";

export default function ChatThread({ messages }) {
  if (!messages.length) {
    return (
      <div className="chat-thread">
        <div className="message message-assistant">
          <div className="avatar" aria-hidden="true">
            <AssistantIcon />
          </div>
          <div className="bubble">
            <p>Ask me to find a drug candidate, e.g. "Find a drug to block Sortilin".</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-thread">
      {messages.map((message) => (
        <div key={message.id} className={`message message-${message.role}`}>
          <div className="avatar" aria-hidden="true">
            {message.role === "user" ? <UserIcon /> : <AssistantIcon />}
          </div>
          <div className="bubble">
            {message.status === "running" && <ToolStatus />}
            <p className={message.status === "error" ? "message-error" : undefined}>{message.content}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
