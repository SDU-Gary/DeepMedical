import { GeistSans } from "geist/font/sans";
import { type Metadata } from "next";

import "~/styles/globals.css";

export const metadata: Metadata = {
  title: "医智寻源",
  description:
    "一个基于人工智能的医学知识图谱搜索引擎，致力于为用户提供精准、快速的医学信息检索服务。",
  icons: [{ rel: "icon", url: "/favicon.ico" }],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${GeistSans.variable}`}>
      <body className="bg-body flex min-h-screen min-w-screen">{children}</body>
    </html>
  );
}
