import { notFound } from 'next/navigation';
import { getMockTailoring, getMockChunks } from '@/mock/loader';
import { TailoringDetail } from '@/components/dashboard/TailoringDetail';

export default async function DemoTailoringPage({
  params,
}: {
  params: Promise<{ tailoringId: string }>;
}) {
  const { tailoringId } = await params;
  const tailoring = getMockTailoring(tailoringId);

  if (!tailoring) notFound();

  return (
    <div className="h-full">
      <TailoringDetail
        readOnly
        initialTailoring={tailoring}
        initialChunks={getMockChunks(tailoringId) ?? undefined}
      />
    </div>
  );
}
