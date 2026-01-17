interface Props {
  title: string;
  items: string[];
}

export default function ResultSection({ title, items }: Props) {
  if (!items || items.length === 0) return null;

  return (
    <section>
      <h3 className="text-lg font-semibold mb-2">{title}</h3>
      <ul className="list-disc pl-5 space-y-1 text-gray-700">
        {items.map((item, idx) => (
          <li key={idx}>{item}</li>
        ))}
      </ul>
    </section>
  );
}
