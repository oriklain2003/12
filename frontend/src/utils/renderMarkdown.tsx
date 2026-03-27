import React from 'react';

/** Parse inline markdown tokens within a text string. */
export function renderInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  // Match **bold**, *italic*, and `code`
  const re = /(\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+?)`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = re.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    if (match[2]) {
      parts.push(<strong key={match.index}>{match[2]}</strong>);
    } else if (match[3]) {
      parts.push(<em key={match.index}>{match[3]}</em>);
    } else if (match[4]) {
      parts.push(<code key={match.index} className="md-inline-code">{match[4]}</code>);
    }
    lastIndex = re.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

/** Parse markdown string into React elements. */
export function renderMarkdown(source: string): React.ReactNode[] {
  const lines = source.split('\n');
  const elements: React.ReactNode[] = [];
  let listItems: React.ReactNode[] = [];
  let listKey = 0;

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(<ul key={`ul-${listKey}`} className="md-list">{listItems}</ul>);
      listItems = [];
      listKey++;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trimStart();

    // Bullet list item: "* ", "- "
    if (/^[*\-]\s+/.test(trimmed)) {
      const content = trimmed.replace(/^[*\-]\s+/, '');
      listItems.push(<li key={i}>{renderInline(content)}</li>);
      continue;
    }

    flushList();

    // Heading: ### / ## / #
    const headingMatch = trimmed.match(/^(#{1,3})\s+(.*)/);
    if (headingMatch) {
      const level = headingMatch[1].length as 1 | 2 | 3;
      const Tag = `h${level}` as const;
      elements.push(<Tag key={i} className={`md-h${level}`}>{renderInline(headingMatch[2])}</Tag>);
      continue;
    }

    // Empty line — skip (spacing handled by CSS)
    if (trimmed === '') continue;

    // Paragraph
    elements.push(<p key={i} className="md-p">{renderInline(trimmed)}</p>);
  }

  flushList();
  return elements;
}
