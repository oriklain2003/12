import { useState, useMemo, useRef, useEffect } from 'react';
import './ResultsTable.css';

interface ResultsTableProps {
  rows: unknown[];
  truncated: boolean;
  selectedRowIndex: number | null;
  onRowSelect: (index: number) => void;
}

export function ResultsTable({ rows, truncated, selectedRowIndex, onRowSelect }: ResultsTableProps) {
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const rowRefs = useRef<(HTMLTableRowElement | null)[]>([]);

  // Auto-detect columns from first row's keys
  const columns = useMemo(() => {
    if (!rows || rows.length === 0) return [];
    const first = rows[0];
    if (typeof first !== 'object' || first === null) return [];
    return Object.keys(first as Record<string, unknown>);
  }, [rows]);

  // Reset sort state when rows reference changes (cube switch safety — Pitfall 6)
  useEffect(() => {
    setSortCol(null);
    setSortDir('asc');
  }, [rows]);

  // Sorted rows
  const sortedRows = useMemo(() => {
    if (!sortCol) return rows;
    return [...rows].sort((a, b) => {
      const rowA = a as Record<string, unknown>;
      const rowB = b as Record<string, unknown>;
      const valA = String(rowA[sortCol] ?? '');
      const valB = String(rowB[sortCol] ?? '');
      const cmp = valA.localeCompare(valB, undefined, { numeric: true });
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [rows, sortCol, sortDir]);

  // Scroll selected row into view when selectedRowIndex changes
  useEffect(() => {
    if (selectedRowIndex !== null) {
      rowRefs.current[selectedRowIndex]?.scrollIntoView({ block: 'nearest' });
    }
  }, [selectedRowIndex]);

  const handleHeaderClick = (col: string) => {
    if (col === sortCol) {
      setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortCol(col);
      setSortDir('asc');
    }
  };

  if (!rows || rows.length === 0) {
    return (
      <div className="results-table__wrapper">
        <div className="results-table__empty">No results</div>
      </div>
    );
  }

  return (
    <div className="results-table__wrapper">
      {truncated && (
        <div className="results-table__truncation-warning">Showing first 100 rows</div>
      )}
      <div className="results-table__scroll">
        <table className="results-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  className="results-table__th"
                  onClick={() => handleHeaderClick(col)}
                >
                  {col}
                  {sortCol === col ? (sortDir === 'asc' ? ' \u2191' : ' \u2193') : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row, i) => (
              <tr
                key={i}
                ref={(el) => { rowRefs.current[i] = el; }}
                className={`results-table__row${selectedRowIndex === i ? ' results-table__row--selected' : ''}`}
                onClick={() => onRowSelect(i)}
              >
                {columns.map((col) => (
                  <td key={col}>
                    {String((row as Record<string, unknown>)[col] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
