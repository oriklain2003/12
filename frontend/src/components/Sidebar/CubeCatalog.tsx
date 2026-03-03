/**
 * Collapsible sidebar with grouped, searchable, draggable cube catalog.
 *
 * - Fetches cube catalog from backend on mount, stores in Zustand
 * - Groups cubes by CubeCategory
 * - Drag handle on each cube card (not the whole card) initiates drag
 * - Collapses to a ~48px icon strip showing one icon per category
 */

import { useEffect, useState } from 'react';
import { CubeCategory } from '../../types/cube';
import type { CubeDefinition } from '../../types/cube';
import { useFlowStore } from '../../store/flowStore';
import { getCatalog } from '../../api/cubes';
import './CubeCatalog.css';

// ─── Category display helpers ─────────────────────────────────────────────────

const CATEGORY_LABELS: Record<CubeCategory, string> = {
  [CubeCategory.DATA_SOURCE]: 'Data Source',
  [CubeCategory.FILTER]: 'Filter',
  [CubeCategory.ANALYSIS]: 'Analysis',
  [CubeCategory.AGGREGATION]: 'Aggregation',
  [CubeCategory.OUTPUT]: 'Output',
};

const CATEGORY_ICONS: Record<CubeCategory, string> = {
  [CubeCategory.DATA_SOURCE]: 'DS',
  [CubeCategory.FILTER]: 'F',
  [CubeCategory.ANALYSIS]: 'A',
  [CubeCategory.AGGREGATION]: 'Ag',
  [CubeCategory.OUTPUT]: 'O',
};

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
    event: React.DragEvent<HTMLSpanElement>,
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
          {'>>'}
        </button>
        <div className="sidebar__icon-strip">
          {CATEGORY_ORDER.map((cat) => (
            <div
              key={cat}
              className="sidebar__category-icon"
              title={CATEGORY_LABELS[cat]}
            >
              {CATEGORY_ICONS[cat]}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ── Expanded state ─────────────────────────────────────────────────────────

  return (
    <div className="sidebar sidebar--expanded glass">
      <div className="sidebar__header">
        <span className="sidebar__title">Cubes</span>
        <button
          className="sidebar__toggle"
          onClick={() => setCollapsed(true)}
          title="Collapse sidebar"
          aria-label="Collapse sidebar"
        >
          {'<<'}
        </button>
      </div>

      <div className="sidebar__search-wrapper">
        <input
          type="text"
          placeholder="Search cubes..."
          className="sidebar__search nodrag"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="sidebar__catalog">
        {catalogLoading && (
          <div className="sidebar__loading">Loading...</div>
        )}

        {!catalogLoading && catalog.length === 0 && (
          <div className="sidebar__empty">No cubes available</div>
        )}

        {CATEGORY_ORDER.map((cat) => {
          const cubes = grouped.get(cat) ?? [];
          if (cubes.length === 0) return null;

          return (
            <div key={cat} className="sidebar__category">
              <div className="sidebar__category-header">
                {CATEGORY_LABELS[cat]}
              </div>
              {cubes.map((cube) => (
                <div key={cube.cube_id} className="sidebar__cube-card">
                  <span
                    className="sidebar__drag-handle"
                    draggable
                    onDragStart={(e) => handleDragStart(e, cube.cube_id)}
                    title="Drag to canvas"
                  >
                    &#8942;&#8942;
                  </span>
                  <div className="sidebar__cube-info">
                    <span className="sidebar__cube-name">{cube.name}</span>
                    <span className="sidebar__cube-desc">{cube.description}</span>
                  </div>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
