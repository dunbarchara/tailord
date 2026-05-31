import type { JobChunk } from '@/types';

/**
 * Returns the Tailwind color class for a chunk's score bar, or null if the
 * chunk should not render a colored bar (gap in public mode, N/A, pending).
 */
export function scoreBarColor(score: number | null, publicMode?: boolean): string | null {
  if (score === 2) return 'bg-score-strong';
  if (score === 1) return publicMode ? 'bg-score-partial-public' : 'bg-score-partial';
  if (score === 0) return publicMode ? null : 'bg-score-gap';
  return null;
}

/**
 * Groups display-ready, render-ready chunks by section for the Job Posting view.
 * Filters out chunks where display_ready is false or should_render is explicitly false.
 */
export function groupBySection(chunks: JobChunk[]): Map<string, JobChunk[]> {
  const groups = new Map<string, JobChunk[]>();
  for (const chunk of chunks) {
    if (!chunk.display_ready) continue;
    if (chunk.should_render === false) continue;
    // Sectionless chunks can't be placed in the posting layout — skip until assigned a section.
    if (!chunk.section) continue;
    const key = chunk.section;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(chunk);
  }
  return groups;
}

/**
 * Groups all non-header, in-bounds chunks by section for the edit / show-hidden view.
 * Uses an empty string as the key for chunks without a section (e.g. overview paragraphs
 * on postings that use bold text instead of ## headings).
 * Pre/post-bounds chunks (excluded_reason set) are excluded — they are page chrome, not job content.
 */
export function groupChunksForAnalysis(chunks: JobChunk[]): Map<string, JobChunk[]> {
  const groups = new Map<string, JobChunk[]>();
  for (const chunk of chunks) {
    if (chunk.chunk_type === 'header') continue;
    if (chunk.excluded_reason === 'pre_content' || chunk.excluded_reason === 'post_content') continue;
    const key = chunk.section ?? '';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(chunk);
  }
  return groups;
}
