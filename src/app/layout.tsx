import type { Metadata } from 'next';
import './globals.css';
import { GlassDroplets } from '@/components/ui/glass/GlassDroplets';

export const metadata: Metadata = {
  title: 'QATRA — Intelligence for Every Drop | Kizuna 2026',
  description: 'AI-Powered Agricultural Intelligence, Smart Irrigation & Farm Operating System for Tunisia & Beyond.',
};

// Applies the saved theme before first paint so there is no light/dark flash.
const themeInitScript = `(function(){try{var t=localStorage.getItem('qatra-theme');if(t==='dark'){document.documentElement.classList.add('dark');}}catch(e){}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr" dir="ltr" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-screen bg-canvas text-ink antialiased selection:bg-brand-500 selection:text-on-accent">
        {/* Background layer: aqua gradient, blobs and glass water droplets (fixed, z-index -1, aria-hidden) */}
        <GlassDroplets />
        {children}
      </body>
    </html>
  );
}
