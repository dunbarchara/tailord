"use client";

import { useState } from "react";
import { JobAnalysis } from "../types/job";
import { analyzeJob, parseJob, submitProfile, submitJob, generateMatch } from "@/lib/api";
import ResultSection from "./ResultSection";

export default function JobAnalyzer() {
    const [url, setUrl] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<JobAnalysis | null>(null);
    const [dataParse, setDataParse] = useState(null);


    const [resume, setResume] = useState("");
    const [github, setGithub] = useState("");
    const [jobUrl, setJobUrl] = useState("");
    const [output, setOutput] = useState(null);

    async function onSubmitProfile() {
        if (!resume) return;
        if (!github) return;

        setLoading(true);
        setError(null);

        try {
            await submitProfile(JSON.stringify({ resume_text: resume, github_username: github }));
        } catch (err: any) {
            setError(err.message || "Something went wrong");
        } finally {
            setLoading(false);
        }
        /*
        await fetch("http://localhost:8000/profile", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ resume_text: resume, github_username: github })
        });*/
    }

    async function onSubmitJob() {
        if (!jobUrl) return;

        setLoading(true);
        setError(null);

        try {
            await submitJob(JSON.stringify({ job_url: jobUrl }));
        } catch (err: any) {
            setError(err.message || "Something went wrong");
        } finally {
            setLoading(false);
        }

        /*
                await fetch("http://localhost:8000/job", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ job_url: jobUrl })
                });*/
    }

    async function onGenerate() {
        console.log("onGenerate enter")

        setLoading(true);
        setError(null);
        setOutput(null);
        console.log("onGenerate after setoutput 1")

        try {
            const data = await generateMatch();
            console.log("onGenerate after generateMatch 1")
            console.log(data);
            setOutput(data);
        } catch (err: any) {
            setError(err.message || "Something went wrong");
        } finally {
            setLoading(false);
        }

        /*
                const res = await fetch("http://localhost:8000/generate", {
                    method: "POST"
                });
                const data = await res.json();
                setOutput(data.content);*/
    }

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

    const onParse = async () => {
        if (!url) return;

        setLoading(true);
        setError(null);
        setDataParse(null);

        try {
            const data = await parseJob(url);
            setDataParse(data);
        } catch (err: any) {
            setError(err.message || "Something went wrong");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="rounded-xl">
            <div className="gap-3 max-w-md">
                <div>
                    <h2 className="text-lg text-zinc-600 dark:text-zinc-300">User Profile</h2>
                    <textarea className="border rounded w-full py-10 text-zinc-600 dark:text-zinc-500" onChange={e => setResume(e.target.value)} placeholder="Paste resume" />
                    <input className="border rounded w-full px-3 py-2 text-zinc-600 dark:text-zinc-500" onChange={e => setGithub(e.target.value)} placeholder="GitHub username" />
                    <button className="w-full mt-1 items-center justify-center gap-2 rounded-full bg-foreground px-5 text-background transition-colors hover:bg-[#383838] dark:hover:bg-[#ccc] md:w-[140px] font-medium hover:cursor-pointer" onClick={onSubmitProfile}>Save Profile</button>
                </div>

                <div className="mt-5">
                    <h2 className="text-lg text-zinc-600 dark:text-zinc-300">Job Posting</h2>
                    <input className="border rounded w-full px-3 py-2 text-zinc-600 dark:text-zinc-500" onChange={e => setJobUrl(e.target.value)} placeholder="Job URL" />
                    <button className="w-full mt-1 items-center justify-center gap-2 rounded-full bg-foreground px-5 text-background transition-colors hover:bg-[#383838] dark:hover:bg-[#ccc] md:w-[140px] font-medium hover:cursor-pointer" onClick={onSubmitJob}>Analyze Job</button>
                </div>

                <div className="mt-5">
                    <h2>Generate Match</h2>
                    <button className="w-full mt-1 items-center justify-center gap-2 rounded-full bg-foreground px-5 text-background transition-colors hover:bg-[#383838] dark:hover:bg-[#ccc] md:w-[140px] font-medium hover:cursor-pointer" onClick={onGenerate}>Generate</button>
                    


                    {output && (
                        <pre className="whitespace-pre-w">
                            {JSON.stringify(output, null, 2)}
                        </pre>
                    )}
                </div>
            </div>


            <div className="mt-15">
                <p className="max-w-md text-lg leading-8 text-zinc-600 dark:text-zinc-300">
                    Paste a job posting URL and extract requirements, skills, and qualifications.
                </p>
            </div>
            <div className="flex gap-3 max-w-md">
                <input
                    type="url"
                    placeholder="https://company.com/jobs/..."
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    className="flex-1 border rounded px-3 py-2 text-zinc-600 dark:text-zinc-500"
                />
                <button
                    onClick={onParse}
                    disabled={loading}
                    className="flex h-12 w-full items-center justify-center gap-2 rounded-full bg-foreground px-5 text-background transition-colors hover:bg-[#383838] dark:hover:bg-[#ccc] md:w-[158px] font-medium hover:cursor-pointer"

                >
                    {loading ? "Parsing..." : "Parse"}
                </button>
            </div>

            {error && (
                <p className="text-red-600 mt-4">{error}</p>
            )}

            {dataParse && (
                <pre className="whitespace-pre-w">
                    {JSON.stringify(dataParse, null, 2)}
                </pre>
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
