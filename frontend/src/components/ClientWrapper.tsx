"use client"

"use client"

import { ReactNode } from "react"
import { SessionProvider } from "next-auth/react"
import { usePathname } from "next/navigation"
import { ThemeProvider } from '@/components/ThemeProvider';
import { Toaster } from '@/components/ui/sonner';

export default function ClientWrapper({ children }: { children: ReactNode }) {
    const pathname = usePathname()
    const forcedLight = pathname.startsWith('/t/') || pathname.startsWith('/u/')

    return (
        <SessionProvider>
            <ThemeProvider forcedLight={forcedLight}>
                {children}
                <Toaster />
            </ThemeProvider>
        </SessionProvider>
    )
}
