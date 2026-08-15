import { useState } from "react";

export default function Composer() {
  const [message, setMessage] = useState("");
  const [extendedThinking, setExtendedThinking] = useState(true);

  function handleSubmit(event) {
    event.preventDefault();
    setMessage("");
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <textarea
        placeholder="Message Acme AI…"
        rows={2}
        value={message}
        onChange={(event) => setMessage(event.target.value)}
      />
      <div className="composer-actions">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={extendedThinking}
            onChange={(event) => setExtendedThinking(event.target.checked)}
          />
          Extended thinking
        </label>
        <button type="submit" className="btn btn-primary">
          Send
        </button>
      </div>
    </form>
  );
}
