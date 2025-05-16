import Markdown from "react-markdown";

import { type Message } from "~/core/messaging";
import { cn } from "~/core/utils";

import { LoadingAnimation } from "./LoadingAnimation";
import { WorkflowProgressView } from "./WorkflowProgressView";

export function MessageHistoryView({
  className,
  messages,
  loading,
}: {
  className?: string;
  messages: Message[];
  loading?: boolean;
}) {
  return (
    <div className={cn(className)}>
      {messages.map((message) => (
        <MessageView key={message.id} message={message} />
      ))}
      {loading && <LoadingAnimation className="mt-8" />}
    </div>
  );
}

function MessageView({ message }: { message: Message }) {
  if (message.type === "text" && message.content) {
    return (
      <div className={cn("flex", message.role === "user" && "justify-end")}>
        <div
          className={cn(
            "relative mb-8 w-fit max-w-[560px] rounded-2xl px-4 py-3 shadow-sm",
            message.role === "user" && "rounded-ee-none bg-primary text-white font-medium",
            message.role === "assistant" && "rounded-es-none bg-white border border-secondary/50",
          )}
        >
          {message.role === "assistant" && (
            <div className="absolute -left-1 -top-1 h-5 w-5 rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center">
              <div className="h-2.5 w-2.5 rounded-full bg-primary/80"></div>
            </div>
          )}
          <Markdown
            components={{
              a: ({ href, children }) => (
                <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  {children}
                </a>
              ),
              p: ({ children }) => (
                <p className="my-1 leading-relaxed">{children}</p>
              ),
              ul: ({ children }) => (
                <ul className="list-disc pl-5 my-2">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="list-decimal pl-5 my-2">{children}</ol>
              ),
              h3: ({ children }) => (
                <h3 className="text-lg font-semibold my-2 text-primary/90">{children}</h3>
              ),
              h4: ({ children }) => (
                <h4 className="text-base font-medium my-1.5 text-primary/80">{children}</h4>
              ),
            }}
          >
            {message.content}
          </Markdown>
        </div>
      </div>
    );
  } else if (message.type === "workflow") {
    console.log(`MessageView: Workflow message ID ${message.id}, message.content:`, JSON.stringify(message.content, null, 2));
    console.log(`MessageView: Workflow message ID ${message.id}, message.content.workflow:`, JSON.stringify(message.content?.workflow, null, 2)); // 使用可选链
    return (
      <WorkflowProgressView
        className="mb-8"
        workflow={message.content.workflow}
      />
    );
  }
  return null;
}
