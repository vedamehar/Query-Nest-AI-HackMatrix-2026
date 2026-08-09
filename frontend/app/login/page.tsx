"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { createSupabaseBrowserClient } from "@/lib/supabase-browser"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import * as z from "zod"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

// Validation schemas
const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(6, "Password must be at least 6 characters"),
})

const signupSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(6, "Password must be at least 6 characters"),
  confirmPassword: z.string().min(6, "Password must be at least 6 characters"),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
})

export default function LoginPage() {
  const router = useRouter()
  const supabase = createSupabaseBrowserClient()
  const [isLoading, setIsLoading] = useState(false)

  // Login form
  const loginForm = useForm<z.infer<typeof loginSchema>>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  })

  // Signup form
  const signupForm = useForm<z.infer<typeof signupSchema>>({
    resolver: zodResolver(signupSchema),
    defaultValues: {
      email: "",
      password: "",
      confirmPassword: "",
    },
  })

  const onLogin = async (values: z.infer<typeof loginSchema>) => {
    setIsLoading(true)
    const { error } = await supabase.auth.signInWithPassword({
      email: values.email,
      password: values.password,
    })

    if (error) {
      toast.error(error.message)
      setIsLoading(false)
    } else {
      toast.success("Identity Verified. Syncing account...")
      router.push("/dashboard")
    }
  }

  const onSignUp = async (values: z.infer<typeof signupSchema>) => {
    setIsLoading(true)
    const { error } = await supabase.auth.signUp({
      email: values.email,
      password: values.password,
    })

    if (error) {
      toast.error(error.message)
      setIsLoading(false)
    } else {
      toast.success("Account created! Check your email to confirm.")
      setIsLoading(false)
    }
  }

  return (
    <div className="flex h-screen w-full overflow-hidden aurora-bg selection:bg-brand-purple/30">
      {/* LEFT SIDE: IMMERSIVE BRANDING (60%) */}
      <div className="hidden lg:flex flex-[1.5] relative flex-col items-center justify-center p-12 overflow-hidden border-r border-white/5">
        <div className="absolute inset-0 bg-gradient-to-br from-brand-purple/5 to-brand-blue/5 animate-pulse" />
        
        {/* Floating Background Glows */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-brand-purple/30 blur-[150px] rounded-full animate-float opacity-50" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-brand-blue/30 blur-[150px] rounded-full animate-float-slow opacity-50" />
        
        <div className="relative z-10 text-center space-y-8 max-w-2xl animate-in fade-in slide-in-from-left-10 duration-1000">
          <div className="inline-flex h-28 w-28 items-center justify-center rounded-[2.5rem] bg-gradient-to-br from-brand-purple to-brand-blue text-white shadow-[0_0_60px_-10px_rgba(139,92,246,0.6)] mx-auto animate-bounce-slow">
            <svg
              className="h-16 w-16"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M13 10V3L4 14h7v7l9-11h-7z"
              />
            </svg>
          </div>
          
          <div className="space-y-4">
            <h1 className="text-7xl font-bold tracking-tighter font-heading text-white drop-shadow-2xl">
              SiteSense <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-purple to-brand-blue">AI</span>
            </h1>
            <p className="text-xl text-slate-400 font-medium tracking-wide max-w-lg mx-auto opacity-80 leading-relaxed">
              Experience the next generation of intelligence. Secure, scalable, and beautifully designed AI support at your fingertips.
            </p>
          </div>
          
          <div className="pt-8 flex items-center justify-center gap-6 opacity-40">
            <div className="h-[1px] w-12 bg-white" />
            <span className="text-xs font-bold tracking-[0.3em] uppercase">Built for Scale</span>
            <div className="h-[1px] w-12 bg-white" />
          </div>
        </div>
      </div>

      {/* RIGHT SIDE: GLASS FORMS / SKELETON (40% or 100% on mobile) */}
      <div className="flex-1 flex flex-col items-center justify-center p-8 lg:p-24 relative z-20 glass-premium shadow-[-40px_0_80px_-40px_rgba(0,0,0,0.5)] overflow-y-auto">
        {isLoading && !loginForm.formState.isSubmitting && !signupForm.formState.isSubmitting ? (
          /* TRANSITION SKELETON (SHUT THE DOORS EFFECT) */
          <div className="w-full max-w-sm space-y-12 animate-in fade-in zoom-in-95 duration-500">
            <div className="space-y-4">
              <div className="h-16 w-4/5 bg-white/10 rounded-2xl animate-pulse" />
              <div className="h-4 w-3/5 bg-white/5 rounded-lg animate-pulse" />
            </div>
            
            <div className="space-y-8 pt-12">
              <div className="space-y-2">
                <div className="h-3 w-24 bg-white/5 rounded-full animate-pulse" />
                <div className="h-14 w-full bg-white/10 rounded-2xl animate-pulse" />
              </div>
              <div className="space-y-2">
                <div className="h-3 w-24 bg-white/5 rounded-full animate-pulse" />
                <div className="h-14 w-full bg-white/10 rounded-2xl animate-pulse" />
              </div>
              <div className="h-16 w-full bg-white/20 rounded-2xl animate-pulse mt-12" />
            </div>
          </div>
        ) : (
          <>
            {/* Mobile Branding */}
            <div className="lg:hidden mb-12 text-center text-white">
              <h1 className="text-4xl font-bold font-heading">SiteSense AI</h1>
            </div>

            <div className="w-full max-w-sm flex flex-col space-y-12 animate-in fade-in slide-in-from-right-10 duration-700">
              <div className="space-y-4 text-left w-full">
                <h2 className="text-5xl font-bold font-heading text-white tracking-tighter">Access Portal</h2>
                <p className="text-slate-400 font-medium tracking-wide opacity-70">Enter your credentials to continue</p>
              </div>

              <Tabs defaultValue="signin" className="w-full flex flex-col">
                <TabsList className="grid w-full grid-cols-2 bg-white/5 border border-white/10 p-1.5 mb-12 rounded-2xl h-14">
                  <TabsTrigger 
                    value="signin" 
                    className="rounded-xl data-[state=active]:bg-brand-purple data-[state=active]:text-white data-[state=active]:shadow-lg h-full transition-all duration-300 font-bold tracking-widest text-[10px]"
                  >
                    SIGN IN
                  </TabsTrigger>
                  <TabsTrigger 
                    value="signup"
                    className="rounded-xl data-[state=active]:bg-brand-purple data-[state=active]:text-white data-[state=active]:shadow-lg h-full transition-all duration-300 font-bold tracking-widest text-[10px]"
                  >
                    SIGN UP
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="signin" className="w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <form onSubmit={loginForm.handleSubmit(onLogin)} className="w-full space-y-10">
                    <div className="w-full space-y-8">
                      <div className="w-full space-y-3">
                        <Label htmlFor="login-email" className="text-[10px] font-black tracking-[0.2em] text-slate-500 uppercase ml-1">Email Address</Label>
                        <Input
                          id="login-email"
                          type="email"
                          placeholder="name@company.com"
                          className="h-14 w-full bg-white/5 border-white/10 rounded-2xl px-6 focus:ring-brand-purple/20 text-white placeholder:text-slate-700"
                          {...loginForm.register("email")}
                          disabled={isLoading}
                        />
                        {loginForm.formState.errors.email && (
                          <p className="text-xs text-red-500/80 ml-1 font-medium italic">
                            {loginForm.formState.errors.email.message}
                          </p>
                        )}
                      </div>
                      <div className="w-full space-y-3">
                        <div className="flex items-center justify-between ml-1">
                          <Label htmlFor="login-password" id="login-password-label" className="text-[10px] font-black tracking-[0.2em] text-slate-500 uppercase">Password</Label>
                          <button type="button" className="text-[10px] text-brand-purple hover:text-white transition-colors font-black uppercase tracking-widest">Forgot?</button>
                        </div>
                        <Input
                          id="login-password"
                          type="password"
                          placeholder="••••••••"
                          className="h-14 w-full bg-white/5 border-white/10 rounded-2xl px-6 focus:ring-brand-purple/20 text-white placeholder:text-slate-700"
                          {...loginForm.register("password")}
                          disabled={isLoading}
                        />
                        {loginForm.formState.errors.password && (
                          <p className="text-xs text-red-500/80 ml-1 font-medium italic">
                            {loginForm.formState.errors.password.message}
                          </p>
                        )}
                      </div>
                    </div>
                    <Button 
                      className="w-full h-16 text-sm font-black tracking-[0.2em] font-heading bg-gradient-to-r from-brand-purple to-brand-blue hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 shadow-[0_20px_40px_-10px_rgba(139,92,246,0.5)] rounded-2xl" 
                      type="submit" 
                      disabled={isLoading}
                    >
                      {isLoading ? "AUTHENTICATING..." : "SIGN IN TO DASHBOARD"}
                    </Button>
                  </form>
                </TabsContent>

                <TabsContent value="signup" className="w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <form onSubmit={signupForm.handleSubmit(onSignUp)} className="w-full space-y-10">
                    <div className="w-full space-y-8">
                      <div className="w-full space-y-3">
                        <Label htmlFor="signup-email" className="text-[10px] font-black tracking-[0.2em] text-slate-500 uppercase ml-1">Work Email</Label>
                        <Input
                          id="signup-email"
                          type="email"
                          placeholder="name@company.com"
                          className="h-14 w-full bg-white/5 border-white/10 rounded-2xl px-6 focus:ring-brand-purple/20 text-white placeholder:text-slate-700"
                          {...signupForm.register("email")}
                          disabled={isLoading}
                        />
                        {signupForm.formState.errors.email && (
                          <p className="text-xs text-red-500/80 ml-1 font-medium italic">
                            {signupForm.formState.errors.email.message}
                          </p>
                        )}
                      </div>
                      <div className="w-full space-y-6">
                        <div className="w-full space-y-3">
                          <Label htmlFor="signup-password" id="signup-password-label" className="text-[10px] font-black tracking-[0.2em] text-slate-500 uppercase ml-1">Password</Label>
                          <Input
                            id="signup-password"
                            type="password"
                            placeholder="••••••••"
                            className="h-14 w-full bg-white/5 border-white/10 rounded-2xl px-6 focus:ring-brand-purple/20 text-white placeholder:text-slate-700"
                            {...signupForm.register("password")}
                            disabled={isLoading}
                          />
                        </div>
                        <div className="w-full space-y-3">
                          <Label htmlFor="confirm-password" id="confirm-password-label" className="text-[10px] font-black tracking-[0.2em] text-slate-500 uppercase ml-1">Confirm Password</Label>
                          <Input
                            id="confirm-password"
                            type="password"
                            placeholder="••••••••"
                            className="h-14 w-full bg-white/5 border-white/10 rounded-2xl px-6 focus:ring-brand-purple/20 text-white placeholder:text-slate-700"
                            {...signupForm.register("confirmPassword")}
                            disabled={isLoading}
                          />
                        </div>
                        {signupForm.formState.errors.confirmPassword && (
                          <p className="text-xs text-red-500/80 ml-1 font-medium italic">
                            {signupForm.formState.errors.confirmPassword.message}
                          </p>
                        )}
                      </div>
                    </div>
                    <Button 
                      className="w-full h-16 text-sm font-black tracking-[0.2em] font-heading bg-gradient-to-r from-brand-purple to-brand-blue hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 shadow-[0_20px_40px_-10px_rgba(139,92,246,0.5)] rounded-2xl" 
                      type="submit" 
                      disabled={isLoading}
                    >
                      {isLoading ? "RESERVING NODE..." : "CREATE PREMIUM ACCOUNT"}
                    </Button>
                  </form>
                </TabsContent>
              </Tabs>

              <div className="text-center pt-8 border-t border-white/5">
                <p className="text-[10px] font-bold tracking-widest text-slate-600 uppercase">
                  By continuing, you agree to our <span className="text-brand-purple hover:text-white cursor-pointer transition-all underline decoration-brand-purple/30">Terms</span> and <span className="text-brand-purple hover:text-white cursor-pointer transition-all underline decoration-brand-purple/30">Privacy</span>.
                </p>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
