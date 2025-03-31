import {
  ArrowUpOutlined,
  GlobalOutlined,
  RobotOutlined,
  MedicineBoxOutlined,
  ExperimentOutlined,
} from "@ant-design/icons";
import { type KeyboardEvent, useCallback, useEffect, useState } from "react";

import { Button } from "~/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "~/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "~/components/ui/tooltip";
import { Atom } from "~/core/icons";
import { setEnabledTeamMembers, useStore } from "~/core/store";
import { cn } from "~/core/utils";

export function InputBox({
  className,
  size,
  responding,
  onSend,
  onCancel,
}: {
  className?: string;
  size?: "large" | "normal";
  responding?: boolean;
  onSend?: (
    message: string,
    options: { deepThinkingMode: boolean; searchBeforePlanning: boolean },
  ) => void;
  onCancel?: () => void;
}) {
  const teamMembers = useStore((state) => state.teamMembers);
  const enabledTeamMembers = useStore((state) => state.enabledTeamMembers);

  const [message, setMessage] = useState("");
  const [deepThinkingMode, setDeepThinkMode] = useState(false);
  const [searchBeforePlanning, setSearchBeforePlanning] = useState(false);
  const [imeStatus, setImeStatus] = useState<"active" | "inactive">("inactive");

  const saveConfig = useCallback(() => {
    localStorage.setItem(
      "deepmedical.config.inputbox",
      JSON.stringify({ deepThinkingMode, searchBeforePlanning }),
    );
  }, [deepThinkingMode, searchBeforePlanning]);

  const handleSendMessage = useCallback(() => {
    if (responding) {
      onCancel?.();
    } else {
      if (message.trim() === "") {
        return;
      }
      if (onSend) {
        onSend(message, { deepThinkingMode, searchBeforePlanning });
        setMessage("");
      }
    }
  }, [
    responding,
    onCancel,
    message,
    onSend,
    deepThinkingMode,
    searchBeforePlanning,
  ]);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      if (responding) {
        return;
      }
      if (
        event.key === "Enter" &&
        !event.shiftKey &&
        !event.metaKey &&
        !event.ctrlKey &&
        imeStatus === "inactive"
      ) {
        event.preventDefault();
        handleSendMessage();
      }
    },
    [responding, imeStatus, handleSendMessage],
  );

  useEffect(() => {
    const config = localStorage.getItem("deepmedical.config.inputbox");
    if (config) {
      const { deepThinkingMode, searchBeforePlanning } = JSON.parse(config);
      setDeepThinkMode(deepThinkingMode);
      setSearchBeforePlanning(searchBeforePlanning);
    }
  }, []);

  useEffect(() => {
    saveConfig();
  }, [deepThinkingMode, searchBeforePlanning, saveConfig]);

  return (
    <div className={cn(className)}>
      <div className="w-full">
        <textarea
          className={cn(
            "m-0 w-full resize-none border-none px-4 py-3 text-lg rounded-t-xl",
            "bg-secondary/30 text-foreground focus:bg-white"
          )}
          style={{
            minHeight: size === "large" ? "8rem" : "1rem", 
            transition: "min-height 600ms ease, background-color 200ms ease"
          }}
          placeholder="请输入您的医学咨询问题..."
          value={message}
          onCompositionStart={() => setImeStatus("active")}
          onCompositionEnd={() => setImeStatus("inactive")}
          onKeyDown={handleKeyDown}
          onChange={(event) => {
            setMessage(event.target.value);
          }}
        />
      </div>
      <div className="flex items-center px-4 py-2 bg-white border-t border-secondary/50">
        <div className="flex grow items-center gap-2">
          <Tooltip>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn("rounded-2xl px-4 text-sm", {
                      "border-primary/30 bg-primary/10 text-primary hover:bg-primary/20 hover:text-primary/90":
                        true,
                    })}
                  >
                    <MedicineBoxOutlined className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-56">
                <DropdownMenuLabel>Agents</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {teamMembers.map((member) => (
                  <Tooltip key={member.name}>
                    <TooltipTrigger asChild>
                      <DropdownMenuCheckboxItem
                        key={member.name}
                        disabled={!member.is_optional}
                        checked={enabledTeamMembers.includes(member.name)}
                        onCheckedChange={() => {
                          setEnabledTeamMembers(
                            enabledTeamMembers.includes(member.name)
                              ? enabledTeamMembers.filter(
                                  (name) => name !== member.name,
                                )
                              : [...enabledTeamMembers, member.name],
                          );
                        }}
                      >
                        {member.name.charAt(0).toUpperCase() +
                          member.name.slice(1)}
                        {member.is_optional && (
                          <span className="text-xs text-gray-400">
                            (Optional)
                          </span>
                        )}
                      </DropdownMenuCheckboxItem>
                    </TooltipTrigger>
                    <TooltipContent side="right">
                      <p>{member.desc}</p>
                    </TooltipContent>
                  </Tooltip>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <TooltipContent>
              <p>启用或禁用agent</p>
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                className={cn("rounded-2xl px-4 text-sm", {
                  "border-primary/30 bg-primary/10 text-primary hover:bg-primary/20 hover:text-primary/90":
                    deepThinkingMode,
                  "border-muted bg-muted/50 text-muted-foreground hover:bg-muted/80":
                    !deepThinkingMode,
                })}
                onClick={() => {
                  setDeepThinkMode(!deepThinkingMode);
                }}
              >
                <ExperimentOutlined className="h-4 w-4 mr-1" />
                <span>深度思考</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>
                深度思考模式。在规划前进行思考。
                <br />
                <span className="text-xxs text-gray-300">
                  该功能可能需要更多token和时间。
                </span>
              </p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                className={cn("rounded-2xl px-4 text-sm", {
                  "border-primary/30 bg-primary/10 text-primary hover:bg-primary/20 hover:text-primary/90":
                    searchBeforePlanning,
                  "border-muted bg-muted/50 text-muted-foreground hover:bg-muted/80":
                    !searchBeforePlanning,
                })}
                onClick={() => {
                  setSearchBeforePlanning(!searchBeforePlanning);
                }}
              >
                <GlobalOutlined className="h-4 w-4 mr-1" />
                <span>联网搜索</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>在规划前搜索</p>
            </TooltipContent>
          </Tooltip>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="icon"
                className={cn(
                  "h-10 w-10 rounded-full transition-colors duration-200",
                  responding ? "bg-destructive/90 text-white hover:bg-destructive" : "bg-primary text-white hover:bg-primary/80",
                )}
                onClick={handleSendMessage}
              >
                {responding ? (
                  <div className="flex h-10 w-10 items-center justify-center">
                    <div className="h-4 w-4 rounded-sm bg-white/80" />
                  </div>
                ) : (
                  <ArrowUpOutlined className="text-white" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>{responding ? "停止执行" : "发送"}</p>
            </TooltipContent>
          </Tooltip>
        </div>
      </div>
    </div>
  );
}
