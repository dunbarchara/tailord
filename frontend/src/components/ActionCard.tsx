import Link from "next/link"

export function ActionCard({ title, href }: { title: string; href: string }) {
  return (
    <Link href={href} className="block border border-border rounded-lg p-6 hover:bg-gray-50">
      <h2 className="text-lg font-medium">{title}</h2>
    </Link>
  )
}
