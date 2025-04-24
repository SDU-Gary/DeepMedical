'use client';

import {
  ForwardedRef,
  HTMLAttributes,
  ReactNode,
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState
} from 'react';
import { cn } from '~/core/utils';

// 类型定义扩展
interface DialogHandle {
    showModal: () => void;
    close: () => void;
  }
// 类型定义
type DialogProps = {
  open: boolean;
  onOpenChange?: (open: boolean) => void;
  children: ReactNode;
  className?: string;
} & HTMLAttributes<HTMLDivElement>;

type DialogContentProps = {
  children: ReactNode;
  className?: string;
} & HTMLAttributes<HTMLDivElement>;

type DialogHeaderProps = HTMLAttributes<HTMLDivElement>;
type DialogTitleProps = HTMLAttributes<HTMLHeadingElement>;
type DialogFooterProps = HTMLAttributes<HTMLDivElement>;

// 对话框根组件
const Dialog = forwardRef<DialogHandle, DialogProps>(
    ({ open = false, onOpenChange, children, className, ...props }, ref) => {
      const [isOpen, setIsOpen] = useState(open);
      const divRef = useRef<HTMLDivElement>(null);
  
      // 同步父组件状态
      useEffect(() => {
        setIsOpen(open);
      }, [open]);
  
      // 暴露组件方法
      useImperativeHandle(ref, () => ({
        showModal: () => {
          setIsOpen(true);
          onOpenChange?.(true);
        },
        close: () => {
          setIsOpen(false);
          onOpenChange?.(false);
        }
      }));
  
      // 键盘事件处理
      useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
          if (e.key === 'Escape') {
            setIsOpen(false);
            onOpenChange?.(false);
          }
        };
  
        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
      }, [onOpenChange]);
  
      if (!isOpen) return null;
  
      return (
        <div
          {...props}
          ref={divRef}
          className={cn(
            
            'fixed inset-0 z-[9999]  flex items-end justify-center',
            className
          )}
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setIsOpen(false);
              onOpenChange?.(false);
            }
          }}
          style={{
            bottom: '20px',
            position: 'fixed',
            ...props.style
          }}
        >
        <div 
          className={cn(
            'relative z-[10000]', // 内容区域更高层级
            'w-[95%] max-w-lg'
          )}
        >
          {children}
        </div>
      </div>
      );
    }
  );
// 对话框内容
const DialogContent = forwardRef<HTMLDivElement, DialogContentProps>(
    ({ children, className, ...props }, ref) => (
      <div
        {...props}
        ref={ref}
        className={cn(
          'bg-background rounded-lg p-6 w-[95%] max-w-lg shadow-xl',
          'border-2 border-border', // 对话框整体边框
        'ring-1 ring-offset-2 ring-primary/10', // 外发光效果
          className
        )}
      >
        {children}
      </div>
    )
  );

// 对话框头部
const DialogHeader = forwardRef(
  ({ className, ...props }: DialogHeaderProps, ref: ForwardedRef<HTMLDivElement>) => (
    <div
      {...props}
      ref={ref}
      className={cn('mb-4 border-b pb-2 flex justify-between items-center', className)}
    />
  )
);

// 对话框标题
const DialogTitle = forwardRef(
  ({ className, ...props }: DialogTitleProps, ref: ForwardedRef<HTMLHeadingElement>) => (
    <h2 {...props} ref={ref} className={cn('text-lg font-semibold', className)} />
  )
);

// 对话框底部
const DialogFooter = forwardRef(
  ({ className, ...props }: DialogFooterProps, ref: ForwardedRef<HTMLDivElement>) => (
    <div
      {...props}
      ref={ref}
      className={cn('mt-6 flex justify-end gap-2', className)}
    />
  )
);

// 导出带类型定义的所有组件
export {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter
};
