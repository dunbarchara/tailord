"use client";

import { useState } from "react";
import { JobAnalysis } from "../types/job";
import { analyzeJob } from "@/lib/api";
import ResultSection from "./ResultSection";

export default function JobAnalyzer() {
    const [url, setUrl] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<JobAnalysis | null>(null);

    const onAnalyze = async () => {
        if (!url) return;

        setLoading(true);
        setError(null);
        setResult(null);

        try {
            const data = await analyzeJob(url);
            setResult(data);
        } catch (err: any) {
            setError(err.message || "Something went wrong");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="rounded-xl">
            <div className="flex gap-3">
                <input
                    type="url"
                    placeholder="https://company.com/jobs/..."
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    className="flex-1 border rounded px-3 py-2 text-zinc-600 dark:text-zinc-500"
                />
                <button
                    onClick={onAnalyze}
                    disabled={loading}
                    className="flex h-12 w-full items-center justify-center gap-2 rounded-full bg-foreground px-5 text-background transition-colors hover:bg-[#383838] dark:hover:bg-[#ccc] md:w-[158px] font-medium hover:cursor-pointer"

                >
                    {loading ? "Analyzing..." : "Analyze"}
                </button>
            </div>

            {error && (
                <p className="text-red-600 mt-4">{error}</p>
            )}

            {result && (
                <div className="mt-8 space-y-6">
                    <div>
                        <h2 className="text-2xl font-semibold">
                            {result.job_title}
                        </h2>
                        <p className="text-gray-500">
                            Seniority: {result.seniority_level}
                        </p>
                    </div>

                    <ResultSection title="Required Skills" items={result.required_skills} />
                    <ResultSection title="Preferred Skills" items={result.preferred_skills} />
                    <ResultSection title="Soft Skills" items={result.soft_skills} />
                    <ResultSection title="Responsibilities" items={result.responsibilities} />
                    <ResultSection title="Qualifications" items={result.qualifications} />
                </div>
            )}
        </div>
    );
}
