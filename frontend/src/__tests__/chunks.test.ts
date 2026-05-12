import { groupBySection, groupChunksForAnalysis, scoreBarColor } from '@/lib/chunks';
import type { JobChunk } from '@/types';

// ---------------------------------------------------------------------------
// scoreBarColor
// ---------------------------------------------------------------------------

describe('scoreBarColor', () => {
  it('returns bg-score-strong for score 2', () => {
    expect(scoreBarColor(2)).toBe('bg-score-strong');
  });

  it('returns bg-score-strong for score 2 in public mode', () => {
    expect(scoreBarColor(2, true)).toBe('bg-score-strong');
  });

  it('returns bg-score-partial for score 1 (private)', () => {
    expect(scoreBarColor(1)).toBe('bg-score-partial');
  });

  it('returns bg-score-partial-public for score 1 in public mode', () => {
    expect(scoreBarColor(1, true)).toBe('bg-score-partial-public');
  });

  it('returns bg-score-gap for score 0 (private)', () => {
    expect(scoreBarColor(0)).toBe('bg-score-gap');
  });

  it('returns null for score 0 in public mode (gap hidden)', () => {
    expect(scoreBarColor(0, true)).toBeNull();
  });

  it('returns null for score -1 (N/A)', () => {
    expect(scoreBarColor(-1)).toBeNull();
  });

  it('returns null for null score (pending)', () => {
    expect(scoreBarColor(null)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeChunk(overrides: Partial<JobChunk> = {}): JobChunk {
  return {
    id: 'chunk-1',
    chunk_type: 'bullet',
    content: 'Some requirement',
    position: 0,
    section: 'Requirements',
    match_score: 1,
    match_rationale: null,
    advocacy_blurb: null,
    experience_source: null,
    experience_sources: null,
    source_label: null,
    is_requirement: true,
    display_ready: true,
    scored_content: null,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// groupBySection (Job Posting view)
// ---------------------------------------------------------------------------

describe('groupBySection', () => {
  it('returns empty map for empty input', () => {
    expect(groupBySection([])).toEqual(new Map());
  });

  it('groups chunks by section', () => {
    const chunks = [
      makeChunk({ id: '1', section: 'Requirements' }),
      makeChunk({ id: '2', section: 'Responsibilities' }),
      makeChunk({ id: '3', section: 'Requirements' }),
    ];
    const groups = groupBySection(chunks);
    expect(groups.get('Requirements')).toHaveLength(2);
    expect(groups.get('Responsibilities')).toHaveLength(1);
  });

  it('skips chunks where display_ready is false', () => {
    const chunks = [
      makeChunk({ id: '1', display_ready: false }),
      makeChunk({ id: '2', display_ready: true }),
    ];
    const groups = groupBySection(chunks);
    expect(groups.get('Requirements')).toHaveLength(1);
    expect(groups.get('Requirements')![0].id).toBe('2');
  });

  it('skips chunks where should_render is explicitly false', () => {
    const chunks = [
      makeChunk({ id: '1', should_render: false }),
      makeChunk({ id: '2', should_render: true }),
      makeChunk({ id: '3' }), // undefined should_render is treated as renderable
    ];
    const groups = groupBySection(chunks);
    expect(groups.get('Requirements')).toHaveLength(2);
  });

  it('preserves order of chunks within a section', () => {
    const chunks = [
      makeChunk({ id: 'a', position: 0 }),
      makeChunk({ id: 'b', position: 1 }),
      makeChunk({ id: 'c', position: 2 }),
    ];
    const result = groupBySection(chunks);
    const ids = result.get('Requirements')!.map((c) => c.id);
    expect(ids).toEqual(['a', 'b', 'c']);
  });

  it('returns empty map when all chunks are filtered out', () => {
    const chunks = [makeChunk({ display_ready: false }), makeChunk({ should_render: false })];
    expect(groupBySection(chunks)).toEqual(new Map());
  });
});

// ---------------------------------------------------------------------------
// groupChunksForAnalysis (Chunk Analysis / debug view)
// ---------------------------------------------------------------------------

describe('groupChunksForAnalysis', () => {
  it('returns empty map for empty input', () => {
    expect(groupChunksForAnalysis([])).toEqual(new Map());
  });

  it('skips header-type chunks', () => {
    const chunks = [
      makeChunk({ id: '1', chunk_type: 'header' }),
      makeChunk({ id: '2', chunk_type: 'bullet' }),
    ];
    const groups = groupChunksForAnalysis(chunks);
    expect(groups.get('Requirements')).toHaveLength(1);
    expect(groups.get('Requirements')![0].id).toBe('2');
  });

  it('uses empty string key for chunks without a section', () => {
    const chunks = [makeChunk({ section: null })];
    const groups = groupChunksForAnalysis(chunks);
    expect(groups.has('')).toBe(true);
  });

  it('includes non-display-ready chunks (unlike groupBySection)', () => {
    const chunks = [makeChunk({ display_ready: false })];
    const groups = groupChunksForAnalysis(chunks);
    expect(groups.get('Requirements')).toHaveLength(1);
  });
});
