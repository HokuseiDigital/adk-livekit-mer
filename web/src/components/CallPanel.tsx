import { useState } from "react"
import {
  BarVisualizer,
  LiveKitRoom,
  RoomAudioRenderer,
  VoiceAssistantControlBar,
  useDataChannel,
  useVoiceAssistant,
} from "@livekit/components-react"
import "@livekit/components-styles"

import { useToken } from "../hooks/useToken"
import type { DebugEvent, TokenResponse } from "../types"

interface CallPanelProps {
  onEvent: (event: DebugEvent) => void
  onReset: () => void
}

export function CallPanel({ onEvent, onReset }: CallPanelProps) {
  const [userName, setUserName] = useState("alice")
  const [session, setSession] = useState<TokenResponse | null>(null)
  const { fetchToken, isPending, error } = useToken()

  const handleStart = async () => {
    onReset()
    const next = await fetchToken(userName.trim() || "guest")
    if (next) setSession(next)
  }

  const handleDisconnected = () => {
    setSession(null)
  }

  if (!session) {
    return (
      <section className="panel">
        <h2>Call</h2>
        <p className="panel__hint">
          Enter a name (used as the LiveKit participant identity and the
          ADK session's <code>user_name</code> state) and start the call.
        </p>
        <label className="panel__label">
          User name
          <input
            value={userName}
            onChange={(e) => setUserName(e.target.value)}
            placeholder="alice"
          />
        </label>
        <button
          className="panel__primary"
          onClick={handleStart}
          disabled={isPending}
        >
          {isPending ? "Connecting…" : "Start call"}
        </button>
        {error && <p className="panel__error">{error}</p>}
        <p className="panel__hint" style={{ marginTop: "1rem" }}>
          Try saying: <em>"What time is it?"</em>,{" "}
          <em>"Look up Bob's email"</em>,{" "}
          <em>"Tell me about LiveKit"</em>, or{" "}
          <em>"Show 'hello from voice' on screen"</em>.
        </p>
      </section>
    )
  }

  return (
    <section className="panel">
      <h2>Call</h2>
      <LiveKitRoom
        serverUrl={session.url}
        token={session.token}
        connect
        audio
        video={false}
        onDisconnected={handleDisconnected}
      >
        <AssistantStage />
        <DataChannelBridge onEvent={onEvent} />
        <div className="panel__controls">
          <VoiceAssistantControlBar />
        </div>
        <RoomAudioRenderer />
      </LiveKitRoom>
    </section>
  )
}

function AssistantStage() {
  const { state, audioTrack } = useVoiceAssistant()
  return (
    <div className="stage">
      <div className="stage__visualizer">
        <BarVisualizer
          state={state}
          trackRef={audioTrack}
          barCount={7}
          options={{ minHeight: 16 }}
        />
      </div>
      <p className="stage__state">
        Agent is <strong>{state}</strong>
      </p>
    </div>
  )
}

function DataChannelBridge({ onEvent }: { onEvent: (e: DebugEvent) => void }) {
  // The worker publishes ADK events and status messages on the default
  // (reliable, unnamed) data channel. Decode each one and forward to
  // the parent. Returning null keeps this purely a side-effect hook.
  useDataChannel((message) => {
    try {
      const decoded = new TextDecoder().decode(message.payload)
      const parsed = JSON.parse(decoded) as DebugEvent
      onEvent({ ...parsed, receivedAt: Date.now() })
    } catch (err) {
      console.warn("could not decode data channel message", err)
    }
  })
  return null
}
