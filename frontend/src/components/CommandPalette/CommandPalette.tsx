/**
 * Command palette (Ctrl/Cmd+K) for quickly adding cubes to the canvas.
 * Fuzzy-searches the catalog by name + description, grouped by category.
 */

import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useReactFlow } from '@xyflow/react';
import { useFlowStore } from '../../store/flowStore';
import { CubeCategory } from '../../types/cube';
import type { CubeDefinition } from '../../types/cube';
import './CommandPalette.css';

// ─── Category display helpers (inline — small constants) ─────────────────────

const CATEGORY_ORDER: CubeCategory[] = [
  CubeCategory.DATA_SOURCE,
  CubeCategory.FILTER,
  CubeCategory.ANALYSIS,
  CubeCategory.AGGREGATION,
  CubeCategory.OUTPUT,
];

const CATEGORY_LABELS: Record<CubeCategory, string> = {
  [CubeCategory.DATA_SOURCE]: 'Data Source',
  [CubeCategory.FILTER]: 'Filter',
  [CubeCategory.ANALYSIS]: 'Analysis',
  [CubeCategory.AGGREGATION]: 'Aggregation',
  [CubeCategory.OUTPUT]: 'Output',
};

// ─── Component ───────────────────────────────────────────────────────────────

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const catalog = useFlowStore((s) => s.catalog);
  const addCubeNode = useFlowStore((s) => s.addCubeNode);
  const { screenToFlowPosition } = useReactFlow();

  const [search, setSearch] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Filter catalog by search
  const filtered = useMemo(() => {
    if (!search) return catalog;
    const q = search.toLowerCase();
    return catalog.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.description.toLowerCase().includes(q)
    );
  }, [catalog, search]);

  // Group by category, preserving order
  const grouped = useMemo(() => {
    const groups: { category: CubeCategory; label: string; cubes: CubeDefinition[] }[] = [];
    for (const cat of CATEGORY_ORDER) {
      const cubes = filtered.filter((c) => c.category === cat);
      if (cubes.length > 0) {
        groups.push({ category: cat, label: CATEGORY_LABELS[cat], cubes });
      }
    }
    return groups;
  }, [filtered]);

  // Flat list of items for keyboard navigation
  const flatItems = useMemo(() => grouped.flatMap((g) => g.cubes), [grouped]);

  // Reset state when opening
  useEffect(() => {
    if (open) {
      setSearch('');
      setActiveIndex(0);
      // Focus on next tick to ensure portal is rendered
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Reset active index when search changes
  useEffect(() => {
    setActiveIndex(0);
  }, [search]);

  // Scroll active item into view
  useEffect(() => {
    if (!listRef.current) return;
    const activeEl = listRef.current.querySelector('.command-palette__item--active');
    activeEl?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  const handleSelect = useCallback(
    (cube: CubeDefinition) => {
      const position = screenToFlowPosition({
        x: window.innerWidth / 2,
        y: window.innerHeight / 2,
      });
      addCubeNode(cube.cube_id, position);
      onClose();
    },
    [screenToFlowPosition, addCubeNode, onClose]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, flatItems.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const item = flatItems[activeIndex];
        if (item) handleSelect(item);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    },
    [flatItems, activeIndex, handleSelect, onClose]
  );

  if (!open) return null;

  let itemIndex = 0;

  return createPortal(
    <>
      <div className="command-palette__backdrop" onClick={onClose} />
      <div className="command-palette__modal" onKeyDown={handleKeyDown}>
        <div className="command-palette__input-wrapper">
          <svg className="command-palette__search-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.3" />
            <path d="M10.5 10.5l3 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
          <input
            ref={inputRef}
            className="command-palette__input"
            placeholder="Search cubes..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <kbd className="command-palette__kbd">ESC</kbd>
        </div>

        <div className="command-palette__results" ref={listRef}>
          {flatItems.length === 0 && (
            <div className="command-palette__empty">No cubes found</div>
          )}

          {grouped.map((group) => (
            <div key={group.category}>
              <div className="command-palette__category-header">{group.label}</div>
              {group.cubes.map((cube) => {
                const idx = itemIndex++;
                return (
                  <div
                    key={cube.cube_id}
                    className={`command-palette__item${idx === activeIndex ? ' command-palette__item--active' : ''}`}
                    onClick={() => handleSelect(cube)}
                    onMouseEnter={() => setActiveIndex(idx)}
                  >
                    <span className="command-palette__item-name">{cube.name}</span>
                    <span className="command-palette__item-desc">{cube.description}</span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </>,
    document.body
  );
}
