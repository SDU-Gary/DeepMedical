import { CheckOutlined, CopyOutlined,DownloadOutlined } from "@ant-design/icons";
import { useState , useEffect} from "react";
import ReactMarkdown, {
  type Options as ReactMarkdownOptions,
} from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";

import { Button } from "~/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "~/components/ui/tooltip";
import { cn } from "~/core/utils";
import { DownloadModal } from "~/app/_components/DownloadModal";

export function Markdown({
  className,
  children,
  style,
  enableCopy,
  ...props
}: ReactMarkdownOptions & {
  className?: string;
  enableCopy?: boolean;
  style?: React.CSSProperties;
}) {
  const [isDownloadModalOpen, setIsDownloadModalOpen] = useState(false);
  const [downloadContent, setDownloadContent] = useState("");

  // 初始化下载内容
  useEffect(() => {
    if (typeof children === "string") {
      setDownloadContent(children);
    }
  }, [children]);
  return (
    <div
      className={cn(className, "markdown flex flex-col gap-4")}
      style={style}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
        {...props}
      >
        {processKatexInMarkdown(children)}
      </ReactMarkdown>
      {enableCopy && typeof children === "string" && (
        <>
          <div className="flex">
          <CopyButton content={children} />


          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="rounded-full"
                onClick={() => setIsDownloadModalOpen(true)}
              >
                <DownloadOutlined className="h-4 w-4 mr-2" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Downlode</TooltipContent>
          </Tooltip>
          </div>
          <DownloadModal
            isOpen={isDownloadModalOpen}
            onClose={() => setIsDownloadModalOpen(false)}
            articleData={{
              title: "DM", // 强制使用默认名称
              content: downloadContent,
              url: window.location.href
            }}
          />
        </>
      )}
    </div>
  );
}
    

function CopyButton({ content }: { content: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="rounded-full"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(content);
              setCopied(true);
              setTimeout(() => {
                setCopied(false);
              }, 1000);
            } catch (error) {
              console.error(error);
            }
          }}
        >
          {copied ? (
            <CheckOutlined className="h-4 w-4" />
          ) : (
            <CopyOutlined className="h-4 w-4" />
          )}{" "}
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        <p>Copy</p>
      </TooltipContent>
    </Tooltip>
  );
}

export function processKatexInMarkdown(markdown?: string | null) {
  if (!markdown) return markdown;

  const markdownWithKatexSyntax = markdown
    .replace(/\\\\\[/g, "$$$$") // Replace '\\[' with '$$'
    .replace(/\\\\\]/g, "$$$$") // Replace '\\]' with '$$'
    .replace(/\\\\\(/g, "$$$$") // Replace '\\(' with '$$'
    .replace(/\\\\\)/g, "$$$$") // Replace '\\)' with '$$'
    .replace(/\\\[/g, "$$$$") // Replace '\[' with '$$'
    .replace(/\\\]/g, "$$$$") // Replace '\]' with '$$'
    .replace(/\\\(/g, "$$$$") // Replace '\(' with '$$'
    .replace(/\\\)/g, "$$$$"); // Replace '\)' with '$$';
  return markdownWithKatexSyntax;
}
