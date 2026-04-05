export default function AuthCodeErrorPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-12">
      <div className="max-w-md space-y-3 rounded-2xl border border-white/10 bg-white/5 p-6 text-center">
        <h1 className="text-lg font-semibold text-white">GitHub sign-in did not complete</h1>
        <p className="text-sm text-body">
          Check your Supabase GitHub provider settings and redirect URLs, then try again.
        </p>
      </div>
    </main>
  );
}
