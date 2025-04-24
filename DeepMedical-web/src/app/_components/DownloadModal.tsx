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
  const [isSubmitting, setIsSubmitting] = useState(false);

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

    // 增强校验逻辑
    if (!merged.content) throw new Error("文档内容不能为空");
    if (merged.content.length < 5) throw new Error("内容需至少5个字符");

    return merged;
  }, [articleData])();

  // 保存文件逻辑
  const saveMarkdownFile = useCallback(async (data: ArticleData) => {
    try {
      const response = await safeFetch("/api/save-as-markdown", {
        method: "POST",
        body: JSON.stringify({
          ...data,
          title: data.title || "DM" // 确保标题存在
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
  
      // 生成规范文件名
      
      const filename = `DM.md`;
  
      // 保存文件（确保传递完整内容）
      await saveMarkdownFile({
        ...mergedArticle,
        title: filename,
        content: mergedArticle.content // 显式传递内容
      });
  
      // 触发下载（添加延迟确保文件生成）
      await new Promise(resolve => setTimeout(resolve, 500));
      
      const link = document.createElement("a");
      link.href = `/api/download/markdown?filename=${encodeURIComponent(filename)}`;
      link.setAttribute("download", filename);
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
  }, [mergedArticle, onClose]);

  useEffect(() => {
    if (!isOpen) setErrorMessage(null);
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

        <div className="space-y-3">
          <Button 
            onClick={handleDownload}
            disabled={isSubmitting}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white"
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