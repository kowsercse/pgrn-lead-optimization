import { AssistantIcon, UserIcon } from "./icons.jsx";
import ToolStatus from "./ToolStatus.jsx";

export default function ChatThread() {
  return (
    <div className="chat-thread">
      <div className="message message-user">
        <div className="avatar" aria-hidden="true">
          <UserIcon />
        </div>
        <div className="bubble">
          <p>Pls find drug to block Sortilin</p>
        </div>
      </div>

      <div className="message message-assistant">
        <div className="avatar" aria-hidden="true">
          <AssistantIcon />
        </div>
        <div className="bubble">
          <ToolStatus />
          <p>Found 5 candidates for docking, starting optimization...</p>
        </div>
      </div>
    </div>
  );
}
