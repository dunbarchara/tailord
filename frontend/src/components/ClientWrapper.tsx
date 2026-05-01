"use client"

import { ReactNode, useEffect } from "react"
import { SessionProvider } from "next-auth/react"
import { usePathname, useRouter } from "next/navigation"
import { ThemeProvider } from '@/components/ThemeProvider';
import { Toaster } from '@/components/ui/sonner';

export default function ClientWrapper({ children }: { children: ReactNode }) {
    const pathname = usePathname()
    const forcedLight = pathname.startsWith('/t/') || pathname.startsWith('/u/')
    const router = useRouter()

    useEffect(() => {
        function handlePageShow(e: PageTransitionEvent) {
            if (e.persisted) router.refresh();
        }
        window.addEventListener('pageshow', handlePageShow);
        return () => window.removeEventListener('pageshow', handlePageShow);
    }, [router]);

    return (
        <SessionProvider>
            <ThemeProvider forcedLight={forcedLight}>
                {children}
                <Toaster />
            </ThemeProvider>
        </SessionProvider>
    )
}
