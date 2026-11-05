import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SeeLess — AI-Powered Audio Description Platform",
  description: "Accessible visual descriptions for movies and videos using Gnani AI.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 min-h-screen flex flex-col antialiased">
        <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
            <a href="/" className="flex items-center gap-2 text-xl font-bold tracking-tight text-white hover:opacity-90">
              <span className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-extrabold text-sm shadow">SL</span>
              <span>See<span className="text-indigo-400">Less</span></span>
            </a>
            <div className="text-xs text-slate-400 border border-slate-800 px-2.5 py-1 rounded-full bg-slate-900">
              Iteration 1 MVP • Powered by Gnani AI
            </div>
          </div>
        </header>

        <main className="flex-1 max-w-6xl w-full mx-auto p-4 sm:p-6 lg:p-8">
          {children}
        </main>

        <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-500">
          SeeLess — AI-Powered Audio Description for Visually Impaired Viewers
        </footer>
      </body>
    </html>
  );
}

