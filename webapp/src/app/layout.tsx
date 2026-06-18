import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";


export const metadata: Metadata = {
  title: "Studio Pro - Image & Image-to-Image Workspace",
  description: "Professional image and image-to-image workspace",
};

function ThemeBootScript() {
  const code = `
    (function () {
      try {
        var saved = window.localStorage.getItem("studio-theme-mode");
        var theme = saved === "light" || saved === "dark"
          ? saved
          : (new Date().getHours() >= 7 && new Date().getHours() < 19 ? "light" : "dark");
        document.documentElement.dataset.theme = theme;
        document.documentElement.classList.toggle("dark", theme === "dark");
        document.documentElement.style.colorScheme = theme;
      } catch (error) {
        document.documentElement.dataset.theme = "dark";
        document.documentElement.classList.add("dark");
      }
    })();
  `;

  return <script dangerouslySetInnerHTML={{ __html: code }} />;
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <ThemeBootScript />
      </head>
      <body className="font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
