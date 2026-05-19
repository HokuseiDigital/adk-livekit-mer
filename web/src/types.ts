export type AdkPart = {
  text?: string | null
  function_call?: { name: string; args: Record<string, unknown> } | null
  function_response?: {
    name: string
    response: Record<string, unknown>
  } | null
}

export type DebugEvent =
  | {
      kind: "adk_event"
      receivedAt: number
      author: string | null
      is_final: boolean | null
      parts?: AdkPart[]
    }
  | {
      kind: "status"
      receivedAt: number
      text: string
    }

export interface TokenResponse {
  url: string
  token: string
  room_name: string
  agent_name: string
}
