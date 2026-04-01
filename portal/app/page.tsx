import LoginForm from '@/components/LoginForm'

export default function HomePage() {
  return (
    <main className="min-h-screen flex items-center justify-center px-4 py-16">
      {/* Ambient glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 overflow-hidden"
      >
        <div className="absolute top-[-20%] left-[30%] w-[500px] h-[500px] rounded-full bg-accent/8 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[20%] w-[400px] h-[400px] rounded-full bg-cyan/5 blur-[100px]" />
      </div>

      <div className="relative w-full max-w-md">
        <LoginForm />
      </div>
    </main>
  )
}
