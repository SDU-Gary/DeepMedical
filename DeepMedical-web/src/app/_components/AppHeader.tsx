import { MedicineBoxOutlined, HeartFilled } from "@ant-design/icons";

export function AppHeader() {
  return (
    <div className="flex items-center w-full justify-between">
      <a
        className="flex items-center font-medium text-xl text-primary transition-colors hover:text-primary/80 group"
        href="https://github.com/SDU-Gary/DeepMedical"
        target="_blank"
      >
        <MedicineBoxOutlined className="mr-2 text-xl group-hover:animate-pulse" />
        <span className="font-serif">DeepMedical</span>
        <HeartFilled className="ml-1.5 text-sm text-primary/70" />
      </a>
      <div className="text-sm text-muted-foreground px-3 py-1 bg-secondary/30 rounded-full">
        医智寻源 · 专业医疗知识检索引擎
      </div>
    </div>
  );
}
