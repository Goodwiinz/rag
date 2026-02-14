export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <main id="main-content" className="min-h-screen bg-[#0a0a0f]">
      {children}
    </main>
  );
}
