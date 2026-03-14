import { Suspense } from 'react';
import { SettingsPanel } from '@/components/dashboard/SettingsPanel';

export default function SettingsPage() {
  return (
    <div className="h-full">
      <Suspense>
        <SettingsPanel />
      </Suspense>
    </div>
  );
}
