import { TailoringDetail } from '@/components/dashboard/TailoringDetail';

export default async function TailoringPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  
  return (
    <div className="h-full">
      <TailoringDetail tailoringId={id} />
    </div>
  );
}
