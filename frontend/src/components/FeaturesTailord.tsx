import Link from 'next/link';

export function FeaturesTailord() {
    return (
        <section className="bg-surface-elevated py-24 sm:py-32">
            <div className="mx-auto max-w-7xl px-6 lg:px-8">
                {/* Value section */}
                <section className="bg-surface-elevated animate-slide-up" style={{ animationDelay: '0.3s' }}>
                    <div className="mx-auto max-w-4xl px-6 text-center">
                        <h2 className="text-3xl font-semibold tracking-tight text-text-primary sm:text-3xl lg:text-4xl">
                            Built for serious job seekers
                        </h2>

                        {/* Subheading */}
                        <p className="mt-6 text-lg leading-8 text-text-secondary max-w-2xl mx-auto">
                            Tailord doesn’t rewrite your resume or spam keywords.
                            It helps you understand your own story — and communicate
                            it clearly to hiring teams.
                        </p>

                        <div className="mt-10 flex justify-center">
                            <Link
                                href="/register"
                                className="group inline-flex items-center gap-2 rounded-lg bg-brand-primary px-6 py-3 font-semibold text-text-inverse shadow-sm hover:bg-brand-primary-hover transition-all hover:shadow-md"
                            >
                                Create your account
                            </Link>
                        </div>
                    </div>
                </section>
            </div>
        </section>
    );
}
