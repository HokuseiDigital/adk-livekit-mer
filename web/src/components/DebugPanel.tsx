import { useEffect, useRef } from "react"
import type { DebugEvent } from "../types"

interface DebugPanelProps {
  events: DebugEvent[]
}

export function DebugPanel({ events }: DebugPanelProps) {
  const listRef = useRef<HTMLOListElement>(null)

  useEffect(() => {
    const node = listRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [events])

  return (
    <section className="panel">
      <h2>ADK events</h2>
      <p className="panel__hint">
        Streamed from the worker via the LiveKit data channel. Each entry is
        one ADK <code>Event</code> from <code>Runner.run_async</code> or a
        status message a tool published back to the UI.
      </p>
      <ol ref={listRef} className="event-list">
        {events.length === 0 && (
          <li className="event-list__empty">
            Waiting for the first turn… start a call and say something.
          </li>
        )}
        {events.map((event, idx) => (
          <li key={idx} className={`event event--${event.kind}`}>
            <EventRow event={event} />
          </li>
        ))}
      </ol>
    </section>
  )
}

function EventRow({ event }: { event: DebugEvent }) {
  const ts = new Date(event.receivedAt).toLocaleTimeString()
  if (event.kind === "status") {
    return (
      <>
        <div className="event__header">
          <span className="event__time">{ts}</span>
          <span className="event__tag event__tag--status">status</span>
        </div>
        <div className="event__body">{event.text}</div>
      </>
    )
  }

  return (
    <>
      <div className="event__header">
        <span className="event__time">{ts}</span>
        <span className="event__tag">{event.author ?? "agent"}</span>
        {event.is_final && (
          <span className="event__tag event__tag--final">final</span>
        )}
      </div>
      {event.parts?.map((part, i) => {
        if (part.text) {
          return (
            <div key={i} className="event__body">
              {part.text}
            </div>
          )
        }
        if (part.function_call) {
          return (
            <div key={i} className="event__body event__body--tool">
              → <strong>{part.function_call.name}</strong>(
              {JSON.stringify(part.function_call.args)})
            </div>
          )
        }
        if (part.function_response) {
          return (
            <div key={i} className="event__body event__body--tool-result">
              ← <strong>{part.function_response.name}</strong> →{" "}
              {JSON.stringify(part.function_response.response)}
            </div>
          )
        }
        return null
      })}
    </>
  )
}
