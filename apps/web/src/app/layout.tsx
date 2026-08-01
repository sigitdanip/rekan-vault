import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'RekanVault — Personal Knowledge & RAG Workspace',
  description: 'Quiet intelligence workspace for personal document search, active memory, and temporal graph reasoning.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#090d16] text-slate-100 antialiased selection:bg-indigo-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}
