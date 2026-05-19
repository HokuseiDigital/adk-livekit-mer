import { useState } from "react"
import { CallPanel } from "./components/CallPanel"
import { DebugPanel } from "./components/DebugPanel"
import type { DebugEvent } from "./types"
import "./App.css"

export default function App() {
  const [events, setEvents] = useState<DebugEvent[]>([])
  const [statusBanner, setStatusBanner] = useState<string | null>(null)

  const handleEvent = (event: DebugEvent) => {
    setEvents((prev) => [...prev, event].slice(-200))
    if (event.kind === "status" && typeof event.text === "string") {
      setStatusBanner(event.text)
    }
  }

  const handleReset = () => {
    setEvents([])
    setStatusBanner(null)
  }

  return (
    <div className="app">
      <header className="app__header">
        <h1>LiveKit + ADK MRE</h1>
        <p>
          Minimum reproducible example of a Google ADK agent driving a
          LiveKit Agents voice worker.
        </p>
      </header>

      {statusBanner && (
        <div className="app__banner">
          <strong>Status from agent:</strong> {statusBanner}
        </div>
      )}

      <main className="app__main">
        <CallPanel onEvent={handleEvent} onReset={handleReset} />
        <DebugPanel events={events} />
      </main>

      <footer className="app__footer">
        Bridge code lives in <code>server/adk_bridge.py</code> — open it
        side-by-side with this UI while reviewing.
      </footer>
    </div>
  )
}
