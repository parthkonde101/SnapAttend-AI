import Link from "next/link";
import { ArrowRight, GraduationCap, ShieldCheck, Sparkles, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Navbar } from "@/components/layout/navbar";

const features = [
  {
    icon: Sparkles,
    title: "Built for speed",
    description: "A streamlined flow designed so taking attendance never eats into class time.",
  },
  {
    icon: ShieldCheck,
    title: "Secure by design",
    description: "Passwords are hashed with bcrypt and every session is protected with JWT authentication.",
  },
  {
    icon: Users,
    title: "Separate portals",
    description: "Purpose-built dashboards for students and teachers, each with the tools they need.",
  },
];

export default function LandingPage() {
  return (
    <div className="flex min-h-dvh flex-col">
      <Navbar />

      <main className="flex-1">
        <section className="container flex flex-col items-center gap-6 py-16 text-center sm:py-32">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/50 px-4 py-1.5 text-sm text-muted-foreground">
            <GraduationCap className="h-4 w-4" />
            Smarter attendance for modern classrooms
          </span>

          <h1 className="max-w-3xl text-balance text-4xl font-bold tracking-tight sm:text-6xl">
            Attendance, simplified with{" "}
            <span className="bg-gradient-to-r from-primary to-[#A53B4C] bg-clip-text text-transparent">
              SnapAttend
            </span>
          </h1>

          <p className="max-w-xl text-balance text-lg text-muted-foreground">
            One platform for students and teachers to manage attendance sessions, accounts, and
            records — clean, fast, and secure.
          </p>

          <div className="flex flex-col gap-3 sm:flex-row">
            <Button asChild size="lg">
              <Link href="/student/login">
                Student Login
                <ArrowRight />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/teacher/login">Teacher Login</Link>
            </Button>
          </div>

          <p className="text-sm text-muted-foreground">
            New student?{" "}
            <Link href="/student/register" className="font-medium text-primary underline-offset-4 hover:underline">
              Create an account
            </Link>
          </p>
        </section>

        <section className="container grid gap-6 pb-24 sm:grid-cols-3">
          {features.map(({ icon: Icon, title, description }) => (
            <Card key={title} className="animate-in">
              <CardHeader>
                <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="h-5 w-5" />
                </div>
                <CardTitle className="text-lg">{title}</CardTitle>
                <CardDescription>{description}</CardDescription>
              </CardHeader>
              <CardContent />
            </Card>
          ))}
        </section>
      </main>

      <footer className="border-t border-border/60 py-8">
        <div className="container flex flex-col items-center justify-between gap-4 text-sm text-muted-foreground sm:flex-row">
          <p>&copy; {new Date().getFullYear()} SnapAttend. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
