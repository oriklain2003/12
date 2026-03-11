/**
 * Collapsible sidebar with grouped, searchable, draggable cube catalog.
 *
 * - Fetches cube catalog from backend on mount, stores in Zustand
 * - Groups cubes by CubeCategory
 * - Entire cube card is draggable
 * - Collapses to a ~48px icon strip showing SVG icons per category
 */

import { useEffect, useState, useRef, useCallback } from 'react';
import { CubeCategory } from '../../types/cube';
import type { CubeDefinition } from '../../types/cube';
import { useFlowStore } from '../../store/flowStore';
import { getCatalog } from '../../api/cubes';
import { Skeleton } from '../ui/Skeleton';
import { NodePreview } from './NodePreview';
import './CubeCatalog.css';

// ─── Category display helpers ─────────────────────────────────────────────────

const CATEGORY_LABELS: Record<CubeCategory, string> = {
  [CubeCategory.DATA_SOURCE]: 'Data Source',
  [CubeCategory.FILTER]: 'Filter',
  [CubeCategory.ANALYSIS]: 'Analysis',
  [CubeCategory.AGGREGATION]: 'Aggregation',
  [CubeCategory.OUTPUT]: 'Output',
};

// SVG category icons
function CategoryIcon({ category, size = 18 }: { category: CubeCategory; size?: number }) {
  const props = { width: size, height: size, viewBox: '0 0 18 18', fill: 'none', stroke: 'currentColor', strokeWidth: 1.4, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };

  switch (category) {
    case CubeCategory.DATA_SOURCE:
      return (
        <svg {...props}>
          <ellipse cx="9" cy="5" rx="6" ry="2.5" />
          <path d="M3 5v8c0 1.38 2.69 2.5 6 2.5s6-1.12 6-2.5V5" />
          <path d="M3 9c0 1.38 2.69 2.5 6 2.5s6-1.12 6-2.5" />
        </svg>
      );
    case CubeCategory.FILTER:
      return (
        <svg {...props}>
          <path d="M2 3h14l-5 6v5l-4 2V9L2 3z" />
        </svg>
      );
    case CubeCategory.ANALYSIS:
      return (
        <svg {...props}>
          <polyline points="2,14 6,8 10,11 16,3" />
          <polyline points="12,3 16,3 16,7" />
        </svg>
      );
    case CubeCategory.AGGREGATION:
      return (
        <svg {...props}>
          <rect x="2" y="10" width="3" height="6" rx="0.5" />
          <rect x="7.5" y="6" width="3" height="10" rx="0.5" />
          <rect x="13" y="2" width="3" height="14" rx="0.5" />
        </svg>
      );
    case CubeCategory.OUTPUT:
      return (
        <svg {...props}>
          <rect x="2" y="3" width="14" height="10" rx="2" />
          <line x1="6" y1="15" x2="12" y2="15" />
        </svg>
      );
  }
}

// Fixed category order for consistent display
const CATEGORY_ORDER: CubeCategory[] = [
  CubeCategory.DATA_SOURCE,
  CubeCategory.FILTER,
  CubeCategory.ANALYSIS,
  CubeCategory.AGGREGATION,
  CubeCategory.OUTPUT,
];

// ─── Component ────────────────────────────────────────────────────────────────

export function CubeCatalog() {
  const catalog = useFlowStore((s) => s.catalog);
  const catalogLoading = useFlowStore((s) => s.catalogLoading);
  const setCatalog = useFlowStore((s) => s.setCatalog);
  const setCatalogLoading = useFlowStore((s) => s.setCatalogLoading);

  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState('');

  // Hover preview state
  const [hoveredCube, setHoveredCube] = useState<CubeDefinition | null>(null);
  const [hoverRect, setHoverRect] = useState<DOMRect | null>(null);
  const hoverTimeout = useRef<ReturnType<typeof setTimeout>>(undefined);

  const handleCubeMouseEnter = useCallback((cube: CubeDefinition, e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    hoverTimeout.current = setTimeout(() => {
      setHoveredCube(cube);
      setHoverRect(rect);
    }, 300);
  }, []);

  const handleCubeMouseLeave = useCallback(() => {
    clearTimeout(hoverTimeout.current);
    setHoveredCube(null);
    setHoverRect(null);
  }, []);

  // Fetch catalog on mount
  useEffect(() => {
    let cancelled = false;
    setCatalogLoading(true);
    getCatalog()
      .then((data) => {
        if (!cancelled) {
          setCatalog(data);
        }
      })
      .catch((err) => {
        console.error('Failed to fetch cube catalog:', err);
      })
      .finally(() => {
        if (!cancelled) {
          setCatalogLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [setCatalog, setCatalogLoading]);

  // Filter cubes by search string
  const filteredCatalog = search
    ? catalog.filter((cube) =>
        cube.name.toLowerCase().includes(search.toLowerCase())
      )
    : catalog;

  // Group filtered cubes by category
  const grouped: Map<CubeCategory, CubeDefinition[]> = new Map();
  for (const cat of CATEGORY_ORDER) {
    grouped.set(cat, []);
  }
  for (const cube of filteredCatalog) {
    const arr = grouped.get(cube.category);
    if (arr) arr.push(cube);
  }

  // ── Drag handler for cube cards ────────────────────────────────────────────

  const handleDragStart = (
    event: React.DragEvent<HTMLDivElement>,
    cubeId: string
  ) => {
    event.dataTransfer.setData('application/cube-id', cubeId);
    event.dataTransfer.effectAllowed = 'move';
  };

  // ── Collapsed state: icon strip ────────────────────────────────────────────

  if (collapsed) {
    return (
      <div className="sidebar sidebar--collapsed glass">
        <button
          className="sidebar__toggle"
          onClick={() => setCollapsed(false)}
          title="Expand sidebar"
          aria-label="Expand sidebar"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M5 3l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <div className="sidebar__icon-strip">
          {CATEGORY_ORDER.map((cat) => (
            <div
              key={cat}
              className="sidebar__category-icon"
              title={CATEGORY_LABELS[cat]}
            >
              <CategoryIcon category={cat} size={18} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ── Expanded state ─────────────────────────────────────────────────────────

  return (
    <div className="sidebar sidebar--expanded glass" data-tour="cube-catalog">
      <div className="sidebar__header">
        <span className="sidebar__title">Cubes</span>
        <button
          className="sidebar__toggle"
          onClick={() => setCollapsed(true)}
          title="Collapse sidebar"
          aria-label="Collapse sidebar"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M9 3l-4 4 4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>

      <div className="sidebar__search-wrapper">
        <svg className="sidebar__search-icon" width="14" height="14" viewBox="0 0 14 14" fill="none">
          <circle cx="6" cy="6" r="4" stroke="currentColor" strokeWidth="1.3" />
          <path d="M9 9l3 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
        </svg>
        <input
          type="text"
          placeholder="Search cubes..."
          className="sidebar__search nodrag"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {search && (
          <button
            className="sidebar__search-clear"
            onClick={() => setSearch('')}
            aria-label="Clear search"
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M2 2l6 6M8 2l-6 6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
            </svg>
          </button>
        )}
      </div>

      <div className="sidebar__catalog">
        {catalogLoading && (
          <div style={{ padding: '0 6px' }}>
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="sidebar__cube-card" style={{ flexDirection: 'column', gap: 6 }}>
                <Skeleton height={14} width="70%" />
                <Skeleton height={10} width="90%" />
              </div>
            ))}
          </div>
        )}

        {!catalogLoading && catalog.length === 0 && (
          <div className="sidebar__empty">No cubes available</div>
        )}

        {(() => { let firstCard = true; return CATEGORY_ORDER.map((cat) => {
          const cubes = grouped.get(cat) ?? [];
          if (cubes.length === 0) return null;

          return (
            <div key={cat} className="sidebar__category">
              <div className="sidebar__category-header">
                {CATEGORY_LABELS[cat]}
              </div>
              {cubes.map((cube) => {
                const isFirstCard = firstCard;
                if (firstCard) firstCard = false;
                return (
                <div
                  key={cube.cube_id}
                  className="sidebar__cube-card"
                  draggable
                  onDragStart={(e) => handleDragStart(e, cube.cube_id)}
                  onMouseEnter={(e) => handleCubeMouseEnter(cube, e)}
                  onMouseLeave={handleCubeMouseLeave}
                  {...(isFirstCard ? { 'data-tour': 'cube-card' } : {})}
                >
                  <div className="sidebar__cube-info">
                    <span className="sidebar__cube-name">{cube.name}</span>
                    <span className="sidebar__cube-desc">{cube.description}</span>
                  </div>
                </div>
              );
              })}
            </div>
          );
        }); })()}
      </div>

      {hoveredCube && hoverRect && (
        <NodePreview cube={hoveredCube} rect={hoverRect} />
      )}
    </div>
  );
}
