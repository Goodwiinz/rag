import { Metadata } from 'next';
import ChatLayoutClient from './chat-layout-client';

export const metadata: Metadata = {
  title: 'Chat',
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <ChatLayoutClient>{children}</ChatLayoutClient>;
}
