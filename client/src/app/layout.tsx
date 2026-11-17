import type { Metadata } from "next";
import "./globals.css";
import PageMotion from "@/components/ui/PageMotion";
import ToastProvider from "@/components/ui/ToastProvider";
export const metadata: Metadata = {
  title: "SocialVerify | Evidence-Based Social & News Verification",
  description: "SocialVerify is an autonomous multi-agent system powered by CrewAI and Google ADK over A2A protocol that collects social-media and news content, extracts and compares claims, verifies evidence using MCP tools, and provides traceable, validated investigation reports.",
  authors: [
    { name: "Suhas Kanwar", url: "https://suhaskanwar.vercel.app" },
  ],
  keywords: [
    "narrative analysis",
    "claim verification",
    "social media monitoring",
    "news analysis",
    "NLP",
    "semantic analysis",
    "data visualization",
    "interactive dashboard",
  ],
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      data-scroll-behavior="smooth"
      className={`h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <ToastProvider>
          <PageMotion>{children}</PageMotion>
        </ToastProvider>
      </body>
    </html>
  );
}
