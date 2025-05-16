import { create } from "zustand";
import { useEffect } from "react";
import { env } from "~/env";

import {
  type ChatEvent,
  chatStream,
  queryTeamMembers,
  type TeamMember,
  initiateChatSession,
  getSessionHistory,
} from "../api";
import { chatStream as mockChatStream } from "../api/mock";
import {
  type WorkflowMessage,
  type Message,
  type TextMessage,
} from "../messaging";
import { clone } from "../utils";
import { WorkflowEngine } from "../workflow";

export const useStore = create<{
  teamMembers: TeamMember[];
  enabledTeamMembers: string[];
  messages: Message[];
  responding: boolean;
  state: {
    messages: { role: string; content: string }[];
  };
  sessionId: string | null;  // 新增会话ID字段
}>(() => ({
  teamMembers: [],
  enabledTeamMembers: [],
  messages: [],
  responding: false,
  state: {
    messages: [],
  },
  sessionId: null,  // 初始化为null
}));

export function useInitTeamMembers() {
  useEffect(() => {
    const enabledTeamMembers = localStorage.getItem(
      "deepmedical.config.enabledTeamMembers",
    );
    void queryTeamMembers().then((teamMembers) => {
      useStore.setState({
        teamMembers,
        enabledTeamMembers: enabledTeamMembers
          ? JSON.parse(enabledTeamMembers)
          : teamMembers.map((member) => member.name),
      });
    });
  }, []);
}

/**
 * 初始化会话，检查本地存储中是否有会话ID，如果有则加载会话历史
 */
export function useInitSession() {
  useEffect(() => {
    // 获取本地存储中的会话ID
    const sessionId = localStorage.getItem("deepmedical.session.id");
    console.log("Checking localStorage for session ID:", sessionId);
    
    if (sessionId) {
      // 设置会话ID到状态
      useStore.setState({ sessionId });
      console.log("Set session ID from localStorage:", sessionId);
      
      // 获取会话历史
      void getSessionHistory(sessionId)
        .then((response) => {
          // 调试步骤1: 打印原始响应数据
          console.log("Raw history response:", JSON.stringify(response, null, 2));
          
          // 格式化消息并添加到状态
          const formattedMessages: Message[] = response.messages.map((msg) => {
            // 调试步骤1-2: 打印消息类型和角色
            console.log(`Message id: ${msg.id}, type: ${msg.type}, role: ${msg.role}`);
            
            // 调试步骤1-3: 打印助手消息的内容结构
            if (msg.role === 'assistant') {
              console.log('Assistant message content (raw):', msg.content);
              console.log('Content type:', typeof msg.content);
              // 如果是对象，打印其结构
              if (typeof msg.content === 'object' && msg.content !== null) {
                console.log('Content keys:', Object.keys(msg.content));
              }
            }
            
            let parsedContent = msg.content;
            if (msg.type === "workflow" && typeof msg.content === 'string') {
              try {
                parsedContent = JSON.parse(msg.content);
                console.log(`Parsed workflow content for message ID ${msg.id}:`, JSON.stringify(parsedContent, null, 2));
              } catch (e) {
                console.error(`Error parsing workflow content for message ID ${msg.id}:`, e, "Raw content:", msg.content);
                // 如果解析失败，保留原始字符串
              }
            }
            
            return {
              id: msg.id,
              type: msg.type as "text" | "workflow",
              role: (msg.role === "system" ? "assistant" : msg.role) as "user" | "assistant",
              content: parsedContent, // 使用解析后的内容
            };
          });
          
          // 调试步骤1-4: 打印格式化后的消息
          console.log('Formatted messages:', formattedMessages);
          
          // 如果有状态信息，也添加到状态
          if (response.state) {
            // 调试步骤2-1: 打印原始状态
            console.log('Original state from response:', response.state);
            
            // 确保state包含messages字段
            const stateWithMessages = {
              ...response.state,
              messages: response.state.messages || []
            };
            
            useStore.setState({ 
              messages: formattedMessages,
              state: stateWithMessages
            });
          } else {
            // 如果没有状态，创建包含空消息数组的状态
            useStore.setState({ 
              messages: formattedMessages,
              state: { messages: [] }
            });
          }
          
          // 调试步骤2-2: 打印状态更新后的store
          const currentState = useStore.getState();
          console.log("Store state after update:", {
            messagesCount: currentState.messages.length,
            messages: currentState.messages,
            state: currentState.state,
            sessionId: currentState.sessionId
          });
          
          console.log("Restored messages from session history:", formattedMessages.length);
        })
        .catch((error) => {
          console.error("Error retrieving session history:", error);
          
          // 检查是否为404错误（会话不存在）
          const is404Error = error.message && error.message.includes("404");
          
          if (is404Error) {
            console.log("Session not found (404), clearing localStorage and preparing for a new session");
          } else {
            console.error("Unexpected error when retrieving session history:", error);
          }
          
          // 无论是何种错误，都清除会话ID并重置状态
          localStorage.removeItem("deepmedical.session.id");
          useStore.setState({
            sessionId: null,
            messages: [],
            state: { messages: [] }
          });
          
          // 在控制台提示用户创建新会话
          console.log("Ready to create a new session. Please send a message to begin.");
        });
    }
  }, []);
}

export function setEnabledTeamMembers(enabledTeamMembers: string[]) {
  useStore.setState({ enabledTeamMembers });
  localStorage.setItem(
    "deepmedical.config.enabledTeamMembers",
    JSON.stringify(enabledTeamMembers),
  );
}

export function addMessage(message: Message) {
  useStore.setState((state) => ({ messages: [...state.messages, message] }));
  return message;
}

export function updateMessage(message: Partial<Message> & { id: string }) {
  useStore.setState((state) => {
    const index = state.messages.findIndex((m) => m.id === message.id);
    if (index === -1) {
      return state;
    }
    const newMessage = clone({
      ...state.messages[index],
      ...message,
    } as Message);
    return {
      messages: [
        ...state.messages.slice(0, index),
        newMessage,
        ...state.messages.slice(index + 1),
      ],
    };
  });
}

export async function sendTextMessage(content: string) {
  // 创建消息对象
  const message: TextMessage = {
    id: Date.now().toString(),
    role: "user",
    type: "text",
    content,
  };

  // 获取当前状态
  const { teamMembers, enabledTeamMembers, state, sessionId } = useStore.getState();
  
  // 如果没有会话ID，先创建一个新会话
  let currentSessionId = sessionId;
  if (!currentSessionId) {
    try {
      console.log("No session ID found, initiating new chat session");
      const sessionResponse = await initiateChatSession(content);
      console.log("Initiated chat session:", sessionResponse);
      
      // 保存会话ID到状态和本地存储
      if (sessionResponse.session_id) {
        currentSessionId = sessionResponse.session_id;
        useStore.setState({ sessionId: currentSessionId });
        try {
          localStorage.setItem("deepmedical.session.id", currentSessionId);
          console.log("Saved session ID to localStorage:", currentSessionId);
        } catch (e) {
          console.error("Error saving session ID to localStorage:", e);
        }
      }
    } catch (error) {
      console.error("Failed to initiate chat session:", error);
      // 如果初始化失败，仍然显示消息但不设置会话ID
    }
  }
  
  // 添加消息到UI
  addMessage(message);

  // 准备聊天流参数
  const enabledMembers = teamMembers
    .filter((member) => enabledTeamMembers.includes(member.name))
    .map((member) => member.name);

  const path = window.location.pathname;
  const isMock = new URLSearchParams(window.location.search).get("mock");
  
  // 创建聊天流
  const stream = isMock
    ? mockChatStream(message)
    : chatStream(
        message,
        state,
        {
          deepThinkingMode: path === "/deep-thinking",
          searchBeforePlanning: path === "/search-first",
          teamMembers: enabledMembers,
          sessionId: currentSessionId || sessionId,  // 使用当前函数中的会话ID或存储中的会话ID
        },
      );
  setResponding(true);

  let textMessage: TextMessage | null = null;
  try {
    // 测试localStorage访问
    try {
      localStorage.setItem("deepmedical.test", "test");
      const test = localStorage.getItem("deepmedical.test");
      console.log("localStorage access test:", test);
      localStorage.removeItem("deepmedical.test");
    } catch (e) {
      console.error("localStorage access error:", e);
    }

    for await (const event of stream) {
      // 打印原始事件对象
      console.log("Raw event received:", JSON.stringify(event, null, 2));
      
      // 处理会话ID事件，这部分已经由initiateChatSession处理，这里作为备用
      if (event.type === "session_id") {
        console.log("Received session_id event via type:", JSON.stringify(event, null, 2));
        
        // 验证event.data结构
        const sessionIdFromEvent = event.data?.session_id; // 使用可选链
        
        // 仅当当前没有会话ID，或者会话ID和事件中的不同时更新
        const currentSessionId = useStore.getState().sessionId;
        if (typeof sessionIdFromEvent === 'string' && sessionIdFromEvent.length > 0 && 
            sessionIdFromEvent !== currentSessionId) {
          console.log("Valid session_id found in event data:", sessionIdFromEvent);
          useStore.setState({ sessionId: sessionIdFromEvent });
          
          try {
            localStorage.setItem("deepmedical.session.id", sessionIdFromEvent);
            console.log("Session ID saved to localStorage:", sessionIdFromEvent);
            
            // 验证保存是否成功
            const savedId = localStorage.getItem("deepmedical.session.id");
            console.log("Verified sessionId in localStorage:", savedId);
          } catch (e) {
            console.error("Error saving sessionId to localStorage:", e);
          }
        } else {
          console.warn("Received session_id event, but session_id is missing, empty, or not a string in data. Event data:", event.data);
        }
        continue; // 处理完会话ID事件后继续处理其他事件
      }
      
      switch (event.type) {
        case "start_of_agent":
          textMessage = {
            id: event.data.agent_id,
            role: "assistant",
            type: "text",
            content: "",
          };
          addMessage(textMessage);
          break;
        case "final_session_state":
          _setWorkflowFinalState({
            messages: event.data.messages,
          });
          break;
        case "message":
          if (textMessage) {
            textMessage.content += event.data.delta.content;
            updateMessage({
              id: textMessage.id,
              content: textMessage.content,
            });
          }
          break;
        case "end_of_agent":
          textMessage = null;
          break;
        case "start_of_workflow":
          const workflowEngine = new WorkflowEngine();
          const workflow = workflowEngine.start(event);
          const workflowMessage: WorkflowMessage = {
            id: event.data.workflow_id,
            role: "assistant",
            type: "workflow",
            content: { workflow: workflow },
          };
          addMessage(workflowMessage);
          for await (const updatedWorkflow of workflowEngine.run(stream)) {
            updateMessage({
              id: workflowMessage.id,
              content: { workflow: updatedWorkflow },
            });
          }
          _setWorkflowFinalState({
            messages: workflow.finalState?.messages ?? [],
          });
          break;
        default:
          break;
      }
    }
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      return;
    }
    throw e;
  } finally {
    setResponding(false);
  }
  return message;
}

/**
 * 清除所有消息并重置会话状态
 */
export function clearMessages() {
  // 重置状态
  useStore.setState({ 
    messages: [], 
    sessionId: null,
    state: { messages: [] }
  });
  
  // 从本地存储中移除会话ID
  try {
    localStorage.removeItem("deepmedical.session.id");
    console.log("Cleared session ID from localStorage");
  } catch (e) {
    console.error("Error clearing session ID from localStorage:", e);
  }
}

export function setResponding(responding: boolean) {
  useStore.setState({ responding });
}

/**
 * 兼容旧版本接口，用于发送消息
 * @param message 消息对象
 * @param params 参数
 * @param options 选项
 * @returns 消息对象
 */
export async function sendMessage(
  message: Message,
  params: {
    deepThinkingMode: boolean;
    searchBeforePlanning: boolean;
  },
  options: { abortSignal?: AbortSignal } = {},
) {
  // 如果是文本消息，使用新的sendTextMessage函数
  if (message.type === "text") {
    return sendTextMessage((message as TextMessage).content);
  }
  
  addMessage(message);
  
  // 获取当前的sessionId
  const { sessionId, enabledTeamMembers, state } = useStore.getState();
  
  let stream: AsyncIterable<ChatEvent>;
  
  if (window.location.search.includes("mock")) {
    stream = mockChatStream(message);
  } else {
    stream = chatStream(
      message,
      state,
      {
        ...params,
        teamMembers: enabledTeamMembers,
        sessionId,
      },
      options,
    );
  }
  
  setResponding(true);
  
  let textMessage: TextMessage | null = null;
  
  try {
    for await (const event of stream) {
      // 处理会话ID事件
      if (event.type === "session_id") {
        const sessionIdFromEvent = event.data?.session_id;
        if (typeof sessionIdFromEvent === 'string' && sessionIdFromEvent.length > 0) {
          useStore.setState({ sessionId: sessionIdFromEvent });
          try {
            localStorage.setItem("deepmedical.session.id", sessionIdFromEvent);
          } catch (e) {
            console.error("Error saving session ID:", e);
          }
        }
      }
      
      // 处理其他事件类型...
      // 这里保持简化实现，主要是为了兼容性
    }
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      return message;
    }
    throw e;
  } finally {
    setResponding(false);
  }
  
  return message;
}

export function _setWorkflowFinalState(state: {
  messages: { role: string; content: string }[];
}) {
  useStore.setState({ state });
}
