"use client";

import { nanoid } from "nanoid";
import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";

import { useAutoScrollToBottom } from "~/components/hooks/useAutoScrollToBottom";
import { TooltipProvider } from "~/components/ui/tooltip";

// 动态导入会在客户端渲染这个组件，避免SSR问题
const ScrollArea = dynamic(
  () => import("~/components/ui/scroll-area").then((mod) => mod.ScrollArea),
  { ssr: false }
);
import { sendMessage, useInitTeamMembers, useStore } from "~/core/store";
import { cn } from "~/core/utils";

import { AppHeader } from "./_components/AppHeader";
import { InputBox } from "./_components/InputBox";
import { MessageHistoryView } from "./_components/MessageHistoryView";

export default function HomePage() {
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const messages = useStore((state) => state.messages);
  const responding = useStore((state) => state.responding);

  const handleSendMessage = useCallback(
    async (
      content: string,
      config: { deepThinkingMode: boolean; searchBeforePlanning: boolean },
    ) => {
      const abortController = new AbortController();
      abortControllerRef.current = abortController;
      await sendMessage(
        {
          id: nanoid(),
          role: "user",
          type: "text",
          content,
        },
        config,
        { abortSignal: abortController.signal },
      );
      abortControllerRef.current = null;
    },
    [],
  );

  useInitTeamMembers();
  useAutoScrollToBottom(scrollAreaRef, responding);
  
  // 是否处于对话模式
  const isConversationMode = messages.length > 0;

  // 使用客户端渲染保护
  const [isMounted, setIsMounted] = useState(false);
  
  // 仅在客户端挂载后渲染完整UI
  useEffect(() => {
    setIsMounted(true);
  }, []);

  // 服务器端或客户端初始渲染时的占位内容
  if (!isMounted) {
    return (
      <div className="h-screen w-full bg-gradient-to-b from-background to-secondary/20 flex items-center justify-center">
        <div className="animate-pulse text-primary">
          <div className="mb-3 p-2 rounded-full bg-primary/10 border border-primary/30">
            <div className="h-16 w-16 rounded-full bg-primary/20"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={150}>
      <ScrollArea className="h-screen w-full bg-gradient-to-b from-background to-secondary/20" ref={scrollAreaRef}>
        <div className="flex min-h-screen flex-col items-center">
          <header className={cn(
            "sticky top-0 right-0 left-0 z-10 flex h-16 w-full items-center px-4 backdrop-blur-md bg-white/60 border-b border-secondary/30",
            "transition-all duration-700 ease-in-out",
            isConversationMode ? "opacity-100" : "opacity-90"
          )}>
            <div className="w-page mx-auto">
              <AppHeader />
            </div>
          </header>
          <main className="w-full flex-1 px-4 pb-48 relative">
            {/* 对话内容视图 */}
            <div 
              className={cn(
                "w-page mx-auto transition-all duration-700 ease-in-out",
                isConversationMode ? "opacity-100 translate-y-0" : "opacity-0 translate-y-12"
              )}
            >
              <MessageHistoryView
                className="w-page mx-auto"
                messages={messages}
                loading={responding}
              />
            </div>

            {/* 首页欢迎内容 - 带有平滑过渡效果 */}
            <div 
              className={cn(
                "absolute left-1/2 transform -translate-x-1/2",
                "transition-all duration-700 ease-in-out",
                isConversationMode 
                  ? "opacity-0 pointer-events-none translate-y-[-20vh]" 
                  : "opacity-100 translate-y-0"
              )}
              style={{ top: "10vh" }}
            >
              <div className="flex w-[640px] flex-col items-center">
                <div className={cn(
                  "mb-3 p-2 rounded-full bg-primary/10 border border-primary/30",
                  "transition-all duration-700 ease-in-out",
                  isConversationMode ? "scale-0" : "scale-100"
                )}>
                  <div className="h-16 w-16 rounded-full bg-primary/20 flex items-center justify-center">
                    <div className="h-10 w-10 relative flex items-center justify-center">
                      <Image 
                        src="/脑电.png" 
                        alt="脑电图"
                        width={32}
                        height={32}
                        className="object-contain"
                      />
                    </div>
                  </div>
                </div>
                <h3 className={cn(
                  "mb-3 text-center text-3xl font-medium text-primary",
                  "transition-all duration-700 ease-in-out",
                  isConversationMode ? "opacity-0 scale-95" : "opacity-100 scale-100"
                )}>
                  赛博华佑，医严定镇
                </h3>
                <div className={cn(
                  "px-4 py-2 rounded-xl bg-white/80 shadow-sm border border-secondary/30 text-center text-lg text-muted-foreground",
                  "transition-all duration-700 ease-in-out",
                  isConversationMode ? "opacity-0 scale-95" : "opacity-100 scale-100"
                )}>
                  <a
                    href="https://github.com/SDU-Gary/DeepMedical"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary font-medium hover:underline"
                  >
                    医智寻源
                  </a>
                  ，一个基于人工智能的医学知识图谱搜索引擎，致力于为用户提供精准、快速的医学信息检索服务。
                </div>
              </div>
            </div>
          </main>

          {/* 输入框容器 - 带有平滑过渡效果 */}
          <footer
            className={cn(
              "fixed",
              "transform-gpu"
            )}
            style={{
              transformOrigin: "center bottom",
              transition: "width 600ms ease, transform 700ms ease, bottom 700ms ease",
              width: isConversationMode ? "var(--width-page)" : "640px",
              bottom: isConversationMode ? "1rem" : "25vh",
              left: isConversationMode ? "50%" : "50%",
              transform: isConversationMode 
                ? "translateX(-50%)" 
                : "translateX(-50%)"
            }}
          >
            <div className="flex flex-col overflow-hidden rounded-[24px] border border-secondary/50 bg-white shadow-lg transition-all duration-700">
              <InputBox
                size={isConversationMode ? "normal" : "large"}
                responding={responding}
                onSend={handleSendMessage}
                onCancel={() => {
                  abortControllerRef.current?.abort();
                  abortControllerRef.current = null;
                }}
              />
            </div>
            <div className="w-page absolute bottom-[-32px] h-8 backdrop-blur-xs" />
            <div className={cn(
              "absolute bottom-[-24px] left-1/2 transform -translate-x-1/2 text-xs text-muted-foreground/70",
              "transition-opacity duration-700 ease-in-out",
              isConversationMode ? "opacity-100" : "opacity-0"
            )}>
              医智寻源 - 提供精准医学知识检索服务
            </div>
          </footer>
        </div>
      </ScrollArea>
    </TooltipProvider>
  );
}
