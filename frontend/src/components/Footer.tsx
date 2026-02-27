export function Footer() {
  return (
    <footer className="border-t border-border-subtle bg-surface-base">
      <div className="mx-auto max-w-7xl px-6 py-12 lg:px-8 lg:py-16">
        <p className="text-xs leading-5 text-text-tertiary">
          &copy; {new Date().getFullYear()} Tailord. All rights reserved.
        </p>
      </div>
    </footer>
  )
}
