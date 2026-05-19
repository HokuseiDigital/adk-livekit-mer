import { useState } from "react"
import type { TokenResponse } from "../types"

const TOKEN_API = import.meta.env.VITE_TOKEN_API_URL ?? "http://localhost:8000"

export function useToken() {
  const [isPending, setIsPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchToken = async (userName: string): Promise<TokenResponse | null> => {
    setIsPending(true)
    setError(null)
    try {
      const res = await fetch(`${TOKEN_API}/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_name: userName }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }
      return (await res.json()) as TokenResponse
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      return null
    } finally {
      setIsPending(false)
    }
  }

  return { fetchToken, isPending, error }
}
