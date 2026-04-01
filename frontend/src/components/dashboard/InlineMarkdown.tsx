// Renders **bold**, *italic*, and [text](url) inline markers as React nodes.
// Links render as their anchor text only (no href) — views using this are for
// reading, not navigation.

export function InlineMarkdown({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={i} className="font-medium text-text-primary">{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith('*') && part.endsWith('*')) {
          return <em key={i}>{part.slice(1, -1)}</em>;
        }
        const linkMatch = part.match(/^\[([^\]]+)\]\([^)]+\)$/);
        if (linkMatch) {
          return <InlineMarkdown key={i} text={linkMatch[1]} />;
        }
        return part;
      })}
    </>
  );
}
