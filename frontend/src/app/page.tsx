"use client"

import { useDarkMode } from "@/hooks/useDarkMode"
import { AuthCard } from "@/components/AuthCard"

import Image from "next/image";
import Link from "next/link"
import JobAnalyzer from "../components/JobAnalyzer";


export default function Home() {
    const { isDark, toggle } = useDarkMode()

    const handleEmailSubmit = (email: string) => {
        alert(`Email submitted: ${email}`)
    }
    return (
        <>
            <main className="min-h-screen bg-[#fafafa] text-gray-900">
                {/* Header with toggle */}
                <header className="border-b border-[var(--border)]">
                    <div className="mx-auto max-w-6xl px-6 py-4 flex justify-between items-center">
                        <span className="font-medium text-xl">Match AI</span>
                        <div className="flex items-center gap-4">
                            <nav className="flex gap-6">
                                <a href="#features" className="text-[var(--muted)] hover:text-[var(--text)] transition">Features</a>
                                <a href="#auth" className="text-[var(--muted)] hover:text-[var(--text)] transition">Sign in</a>
                            </nav>
                            {/* Dark mode toggle */}
                            <button
                                onClick={toggle}
                                className="px-3 py-1 rounded-lg border border-[var(--border)] hover:bg-[var(--stack-100)] transition"
                            >
                                {isDark ? "Light Mode" : "Dark Mode"}
                            </button>
                        </div>
                    </div>
                </header>

                {/* Hero */}
                <section className="mx-auto max-w-4xl px-6 pt-28 pb-24 text-center">
                    <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight leading-tight">
                        Understand how your experience
                        <br />
                        fits any job — instantly
                    </h1>

                    <p className="mt-6 text-lg text-gray-600">
                        Tailord analyzes your background and job postings to clearly
                        explain why you’re a strong candidate — and how to position
                        yourself with confidence.
                    </p>

                    {/* AuthCard */}
                    <section id="auth" className="flex justify-center mb-20">
                        <AuthCard
                            title="Get started"
                            googleText="Sign in with Google"
                            emailText="Continue with email"
                            onEmailSubmit={handleEmailSubmit}
                        />
                    </section>

                    <div className="mt-10 flex justify-center gap-4">
                        <Link
                            href="/register"
                            className="rounded-lg bg-gray-900 px-6 py-3 text-white hover:bg-gray-800"
                        >
                            Try Tailord
                        </Link>
                        <Link
                            href="#how-it-works"
                            className="rounded-lg border border-gray-300 px-6 py-3 text-gray-700 hover:bg-gray-100"
                        >
                            Learn more
                        </Link>
                    </div>
                </section>

                {/* How it works */}
                <section
                    id="how-it-works"
                    className="mx-auto max-w-5xl px-6 pb-28"
                >
                    <div className="grid gap-12 sm:grid-cols-3">
                        <Feature
                            title="Bring your experience"
                            description="Upload your resume, connect GitHub, or add context in your own words. We build a complete picture of your background."
                        />
                        <Feature
                            title="Paste a job posting"
                            description="Provide a job URL. We extract what the role is really asking for — skills, expectations, and signals."
                        />
                        <Feature
                            title="Get a clear match narrative"
                            description="See how your experience aligns, where you stand out, and how to explain your fit in interviews."
                        />
                    </div>
                </section>

                {/* Value section */}
                <section className="bg-white border-t border-gray-200">
                    <div className="mx-auto max-w-4xl px-6 py-24 text-center">
                        <h2 className="text-3xl font-semibold tracking-tight">
                            Built for serious job seekers
                        </h2>

                        <p className="mt-6 text-lg text-gray-600">
                            Tailord doesn’t rewrite your resume or spam keywords.
                            It helps you understand your own story — and communicate
                            it clearly to hiring teams.
                        </p>

                        <div className="mt-10 flex justify-center">
                            <Link
                                href="/register"
                                className="rounded-lg bg-gray-900 px-6 py-3 text-white hover:bg-gray-800"
                            >
                                Create your account
                            </Link>
                        </div>
                    </div>
                </section>

                {/* Footer */}
                <footer className="border-t border-gray-200">
                    <div className="mx-auto max-w-6xl px-6 py-8 text-sm text-gray-500 flex justify-between">
                        <span>© {new Date().getFullYear()} Tailord</span>
                        <span>Built for clarity, not hype</span>
                    </div>
                </footer>
            </main>
        </>
    );
}

function Feature({
    title,
    description,
}: {
    title: string
    description: string
}) {
    return (
        <div>
            <h3 className="text-lg font-medium">{title}</h3>
            <p className="mt-2 text-gray-600 leading-relaxed">
                {description}
            </p>
        </div>
    )
}
