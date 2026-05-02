import data from './data.json';
import type { TailoringListItem, Tailoring, ExperienceRecord, ChunksResponse, ExperienceChunksResponse } from '@/types';

export function getMockDisplayName(): string {
  return data.displayName;
}

export function getMockUser() {
  return data.user;
}

export function getMockTailorings(): TailoringListItem[] {
  return data.tailorings as TailoringListItem[];
}

export function getMockExperience(): ExperienceRecord {
  return data.experience as unknown as ExperienceRecord;
}

export function getMockTailoring(id: string): Tailoring | null {
  const details = data.tailoringDetails as Record<string, unknown>;
  return (details[id] ?? null) as Tailoring | null;
}

export function getMockChunks(id: string): ChunksResponse | null {
  const chunks = data.chunks as Record<string, unknown>;
  return (chunks[id] ?? null) as ChunksResponse | null;
}

export function getMockExperienceChunks(): ExperienceChunksResponse {
  return (data as unknown as { experienceChunks: ExperienceChunksResponse }).experienceChunks;
}
