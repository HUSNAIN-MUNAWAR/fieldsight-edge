import type { Metadata } from 'next';
import './globals.css';
import { QueryProvider } from '../components/query-provider';

export const metadata: Metadata = { title: 'FieldSight Edge', description: 'Industrial AI inspection control center' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><QueryProvider>{children}</QueryProvider></body></html>;
}
