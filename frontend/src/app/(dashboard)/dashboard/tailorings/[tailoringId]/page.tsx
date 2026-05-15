import { TailoringDetail } from '@/components/dashboard/TailoringDetail';

export const dynamic = 'force-dynamic';

export default async function TailoringPage({
  params,
}: {
  params: Promise<{ tailoringId: string }>;
}) {
  const { tailoringId } = await params;

  return (
    <div className="h-full">
      <TailoringDetail tailoringId={tailoringId} />
    </div>
  );
}
