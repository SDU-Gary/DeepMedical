declare module '@/components/ui/dialog' {
    export * from '~/components/ui/dialog';
    
    interface DialogProps {
      open?: boolean;
      onOpenChange?: (open: boolean) => void;
    }
    
    interface DialogHeaderProps {
      children: React.ReactNode;
    }
    
    interface DialogTitleProps {
      children: React.ReactNode;
    }
  }