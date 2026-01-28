'use client';

import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { AuthCard } from "@/components/AuthCard"

export function Hero() {

    const handleEmailSubmit = (email: string) => {
        alert(`Email submitted: ${email}`)
    }
    return (
        <>
            
            <section className="relative overflow-hidden px-6 pt-14 lg:px-8 lg:pt-20">
                <div className="mx-auto max-w-4xl text-center pb-24 lg:pb-24">
                    {/* Main heading */}
                    <h1 className="text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl lg:text-5xl animate-slide-up">
                        Understand how your experience
                        <br />
                        fits any job — instantly
                    </h1>

                    {/* Subheading */}
                    <p className="mt-6 text-lg leading-8 text-text-secondary max-w-2xl mx-auto animate-slide-up" style={{ animationDelay: '0.1s' }}>
                        Tailord analyzes your background and job postings to clearly
                        explain why you’re a strong candidate — and how to position
                        yourself with confidence.
                    </p>

                    {/* CTA buttons */}
                    <div className="mt-10 flex items-center justify-center gap-x-4 animate-slide-up" style={{ animationDelay: '0.2s' }}>
                        <Link
                            href="/register"
                            className="group inline-flex items-center gap-2 rounded-md bg-brand-primary px-6 py-3 text-sm font-semibold text-text-inverse shadow-sm hover:bg-brand-primary-hover transition-all hover:shadow-md"
                        >
                            Try Tailord
                            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                        </Link>
                        <Link
                            href="#how-it-works"
                            className="inline-flex items-center rounded-md bg-surface-elevated px-6 py-3 text-sm font-semibold text-text-primary shadow-sm ring-1 ring-inset ring-border-default hover:bg-surface-overlay transition-colors"
                        >
                            Learn More
                        </Link>
                    </div>

                    {/* Trust indicators */}
                    {/*
                    <div className="mt-16 flex flex-col items-center gap-4 animate-fade-in" style={{ animationDelay: '0.3s' }}>
                        <p className="text-sm text-text-tertiary">Trusted by teams at</p>
                        <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-4 opacity-60">
                            
                            {['Company 1', 'Company 2', 'Company 3', 'Company 4'].map((company, i) => (
                                <div
                                    key={company}
                                    className="h-8 w-24 bg-text-tertiary/20 rounded"
                                    style={{ animationDelay: `${0.4 + i * 0.1}s` }}
                                />
                            ))}
                        </div>
                    </div>*/}
                </div>

                {/* How it works */}
                <section
                    id="how-it-works"
                    className="mx-auto max-w-5xl px-6 pb-28 animate-slide-up" style={{ animationDelay: '0.2s' }}
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

            </section>
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
            <h3 className="text-lg font-medium text-text-primary">{title}</h3>
            <p className="mt-2 leading-relaxed text-text-secondary">
                {description}
            </p>
        </div>
    )
}