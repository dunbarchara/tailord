import { getMockTailorings, getMockDisplayName } from '@/mock/loader';
import { DashboardHome } from '@/components/dashboard/DashboardHome';

export default function DemoDashboardPage() {
  return (
    <div className="h-full">
      <DashboardHome
        name={getMockDisplayName()}
        tailorings={getMockTailorings()}
        basePath="/demo/dashboard"
        readOnly
      />
    </div>
  );
}
