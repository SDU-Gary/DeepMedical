import { Button } from '~/components/ui/button';
import { DownloadOutlined } from '@ant-design/icons';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { useState, useEffect, useCallback } from "react";
import { toast } from 'react-hot-toast';

type ArticleData = {
  title: string;
  content: string;
  url?: string;
};

type DownloadModalProps = {
  isOpen: boolean;
  onClose: () => void;
  articleData?: Partial<ArticleData>;
};

async function safeFetch(input: RequestInfo, init?: RequestInit) {
  try {
    const response = await fetch(input, {
      ...init,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        ...init?.headers
      }
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`[${response.status}] ${errorText.slice(0, 200)}`);
    }
    return response;
  } catch (error) {
    console.error('Network Error:', error);
    throw error;
  }
}

export function DownloadModal({ isOpen, onClose, articleData }: DownloadModalProps) {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [filenameError, setFilenameError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [customFilename, setCustomFilename] = useState<string>('DM');

  // 数据合并与校验
  const mergedArticle = useCallback(() => {
    const defaultData = {
      title: "DM",
      content: "",
      url: window.location.href
    };

    const merged = {
      ...defaultData,
      ...articleData,
      title: (articleData?.title || defaultData.title).trim(),
      content: (articleData?.content || defaultData.content).trim()
    };

    if (!merged.content) throw new Error("文档内容不能为空");
    if (merged.content.length < 5) throw new Error("内容需至少5个字符");

    return merged;
  }, [articleData])();

  // 文件名校验
  const validateFilename = useCallback((name: string): string => {
    const sanitizedName = name
    .replace(/[^\w\u4e00-\u9fa5\-_.]/g, '_') // 修改正则匹配范围
    .replace(/_+/g, '_')
    .slice(0, 120) // 与后端长度限制一致
    .replace(/^_+|_+$/g, '');
    
    return sanitizedName ? `${sanitizedName}.md` : 'DM.md';
  }, []);

  // 保存文件逻辑
  const saveMarkdownFile = useCallback(async(data: ArticleData & { filename: string }) => {
    try {
      const response = await safeFetch("/api/save-as-markdown", {
        method: "POST",
        body: JSON.stringify({
          ...data,
          filename: data.filename // 添加文件名参数
        })
      });
      return response.json();
    } catch (error) {
      console.error("保存失败详情:", error);
      throw new Error(error instanceof Error ? error.message : "保存操作失败");
    }
  }, []);

  // 下载处理流程
  const handleDownload = useCallback(async () => {
    try {
      setIsSubmitting(true);
      setErrorMessage(null);
      setFilenameError(null);

      

      // 校验并处理文件名
      const processedFilename = validateFilename(customFilename);
      if (processedFilename !== customFilename) {
        setFilenameError('文件名包含非法字符，已自动修正');
      }

      // 生成最终文件名
      const filename = processedFilename.replace('.md', ''); // 移除扩展名用于标题
      
      // 保存文件
      // 保存文件并获取服务端返回的真实文件名
    const saveResult = await saveMarkdownFile({
      ...mergedArticle,
      filename: processedFilename,
      content: mergedArticle.content
    });
    if (saveResult.status === 'error') {
      throw new Error(saveResult.message || "文件保存失败");
    }
    // 使用服务端返回的文件名（关键修改）
    const serverFilename = saveResult.saved_filename; 

      // 触发下载
      await new Promise(resolve => setTimeout(resolve, 500));
      
      const link = document.createElement("a");
      link.href = `/api/download/markdown?filename=${encodeURIComponent(processedFilename)}`;
      link.setAttribute("download", serverFilename);
      document.body.appendChild(link);
      link.click();
      link.remove();

      toast.success("文件下载已开始");
      onClose();
    } catch (error) {
      const message = error instanceof Error ? error.message : "未知错误";
      setErrorMessage(message);
      toast.error(`下载失败: ${message}`);
    } finally {
      setIsSubmitting(false);
    }
  }, [mergedArticle, onClose, customFilename, validateFilename]);

  // 重置状态
  useEffect(() => {
    if (!isOpen) {
      setCustomFilename('DM');
      setFilenameError(null);
    }
  }, [isOpen]);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="z-[9999] max-w-[425px]">
        <DialogHeader>
          <DialogTitle className="text-lg">文档下载</DialogTitle>
        </DialogHeader>

        {errorMessage && (
          <div className="mb-4 p-3 bg-red-50 text-red-600 rounded-md text-sm">
            {errorMessage}
          </div>
        )}

        {/* 新增文件名输入 */}
        <div className="space-y-3 mb-4">
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="输入文件名（默认：DM）"
              value={customFilename}
              onChange={(e) => setCustomFilename(e.target.value)}
              className="flex-1 px-4 py-2 border rounded-md focus:ring-2 focus:#0077b6"
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleDownload();
              }}
            />
          </div>
          
          {filenameError && (
            <p className="text-sm text-red-600">{filenameError}</p>
          )}
        </div>

        <div className="space-y-3">
          <Button 
            onClick={handleDownload}
            disabled={isSubmitting}
            className="w-full hover:#0077b6 text-white"
          >
            {isSubmitting ? (
              <span className="flex items-center">
                <DownloadOutlined className="animate-bounce mr-2" />
                生成文件中...
              </span>
            ) : "立即下载"}
          </Button>
          
          <Button 
            variant="outline" 
            onClick={onClose}
            className="w-full border-gray-300 hover:bg-gray-50"
          >
            取消操作
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}