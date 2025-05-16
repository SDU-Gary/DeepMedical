import { env } from "~/env";

import { type Message } from "../messaging";
import { fetchStream } from "../sse";

import { type TeamMember, type ChatEvent } from "./types";

export function chatStream(
  userMessage: Message,
  state: { messages: { role: string; content: string }[] },
  params: {
    deepThinkingMode: boolean;
    searchBeforePlanning: boolean;
    teamMembers: string[];
    sessionId?: string | null;  // 修改类型为string | null
  },
  options: { abortSignal?: AbortSignal } = {},
) {
  return fetchStream<ChatEvent>(
    (env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api") + "/chat/stream",
    {
      body: JSON.stringify({
        messages: [userMessage],
        deep_thinking_mode: params.deepThinkingMode,
        search_before_planning: params.searchBeforePlanning,
        debug:
          location.search.includes("debug") &&
          !location.search.includes("debug=false"),
        team_members: params.teamMembers,
        session_id: params.sessionId,  // 传递sessionId给后端
      }),
      signal: options.abortSignal,
    },
  );
}

/**
 * 初始化聊天会话
 * @param message 初始消息内容
 * @returns 包含会话ID的响应
 */
export async function initiateChatSession(message: string) {
  try {
    const response = await fetch(
      (env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api") + "/chat/initiate",
      { 
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: message
        }) 
      }
    );
    
    if (!response.ok) {
      throw new Error(`Failed to initiate chat session: ${response.status}`);
    }
    
    return await response.json() as { 
      session_id: string;
      initial_messages: any[];
      status: string;
    };
  } catch (error) {
    console.error("Error initiating chat session:", error);
    throw error;
  }
}

/**
 * 获取会话历史
 * @param sessionId 会话ID
 * @returns 会话历史记录
 */
export async function getSessionHistory(sessionId: string) {
  try {
    const response = await fetch(
      (env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api") + 
      `/session/${sessionId}/history`,
      { method: "GET" }
    );
    
    if (!response.ok) {
      throw new Error(`Failed to get session history: ${response.status}`);
    }
    
    return await response.json() as {
      session_id: string;
      messages: Array<{
        id: string;
        role: string;
        type: string;
        content: any;
      }>;
      state?: Record<string, any>;
    };
  } catch (error) {
    console.error(`Error getting history for session ${sessionId}:`, error);
    throw error;
  }
}

export async function queryTeamMembers() {
  try {
    const response = await fetch(
      (env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api") +
        "/team_members",
      { method: "GET" },
    );
    const { team_members } = (await response.json()) as {
      team_members: Record<string, TeamMember>;
    };
    const allTeamMembers = Object.values(team_members);
    return [
      ...allTeamMembers.filter((member) => !member.is_optional),
      ...allTeamMembers.filter((member) => member.is_optional),
    ];
  } catch (err) {
    console.warn(
      "🖐️️ [deepmedical]\n\nError connecting to deepmedical backend. Please ensure the latest version is running locally. See: https://github.com/deepmedical/deepmedical.\n\nRaw network error: ",
    );
    console.error(err);
    return [];
  }
}
