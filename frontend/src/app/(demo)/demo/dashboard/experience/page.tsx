import { getMockExperience, getMockExperienceChunks } from '@/mock/loader';
import { ExperienceManager } from '@/components/dashboard/ExperienceManager';

export default function DemoExperiencePage() {
  return (
    <div className="h-full">
      <ExperienceManager
        readOnly
        initialRecord={getMockExperience()}
        initialChunks={getMockExperienceChunks()}
      />
    </div>
  );
}
