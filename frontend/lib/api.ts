export interface ApiResponse {
  response: string;
  model_used?: string;
  latency_ms?: number;
}

export const getSessionId = (): string => {
  if (typeof window === "undefined") return "";
  let sessionId = sessionStorage.getItem("alucard_session_id");
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    sessionStorage.setItem("alucard_session_id", sessionId);
  }
  return sessionId;
};

export const sendMessage = async (message: string): Promise<ApiResponse> => {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://ai-bot-tp8d.onrender.com";
  if (!apiUrl) {
    throw new Error("NEXT_PUBLIC_API_URL is not defined");
  }

  const sessionId = getSessionId();

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 90000); // 90 seconds

  try {
    const res = await fetch(`${apiUrl}/chat/alucard`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message, session_id: sessionId }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      throw new Error(`API error: ${res.status}`);
    }

    return await res.json();
  } catch (error: unknown) {
    clearTimeout(timeoutId);
    console.error("Chat API Error:", error);
    if (error instanceof Error && error.name === "AbortError") {
      throw error;
    }
    throw new Error("THE SYSTEM IS UNRESPONSIVE.");
  }
};
