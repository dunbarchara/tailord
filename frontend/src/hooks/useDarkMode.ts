"use client"

import { useEffect, useState } from "react"

export function useDarkMode() {
  const [isDark, setIsDark] = useState(false)

  useEffect(() => {
    // Initialize from system preference or localStorage
    const stored = localStorage.getItem("theme")
    if (stored === "dark") setIsDark(true)
    else if (stored === "light") setIsDark(false)
    else setIsDark(window.matchMedia("(prefers-color-scheme: dark)").matches)
  }, [])

  useEffect(() => {
    const root = window.document.documentElement
    if (isDark) root.classList.add("dark")
    else root.classList.remove("dark")

    localStorage.setItem("theme", isDark ? "dark" : "light")
  }, [isDark])

  const toggle = () => setIsDark((prev) => !prev)

  return { isDark, toggle }
}
