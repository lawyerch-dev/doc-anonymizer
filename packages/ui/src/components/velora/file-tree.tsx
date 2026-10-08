"use client";

import { useState } from "react";

import { cn } from "../../lib/utils";

export interface FileNode {
  name: string;
  /** Presence of `children` makes the node a folder */
  children?: FileNode[];
  /** Folders start open unless this is false */
  defaultOpen?: boolean;
}

interface FileTreeProps {
  tree: FileNode[];
  className?: string;
}

function Node({ node, depth }: { node: FileNode; depth: number }) {
  const isFolder = Array.isArray(node.children);
  const [open, setOpen] = useState(node.defaultOpen ?? true);

  return (
    <li>
      <div
        style={{ paddingLeft: depth * 14 }}
        className="flex items-center gap-1.5 rounded-md py-1 pr-2 text-sm"
      >
        {isFolder ? (
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            className="flex flex-1 cursor-pointer items-center gap-1.5 rounded-md px-1 py-0.5 text-left transition-colors hover:bg-muted"
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
              className={cn(
                "shrink-0 text-muted-foreground transition-transform duration-150 motion-reduce:transition-none",
                open && "rotate-90"
              )}
            >
              <path d="M4.5 2.5L8 6l-3.5 3.5" />
            </svg>
            <span className="font-medium">{node.name}</span>
          </button>
        ) : (
          <span className="flex items-center gap-1.5 px-1 py-0.5 pl-[1.125rem] text-muted-foreground">
            {node.name}
          </span>
        )}
      </div>

      {isFolder && open && (
        <ul>
          {node.children!.map((child) => (
            <Node key={child.name} node={child} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
}

/**
 * Collapsible file tree for documenting project structure. Renders as nested
 * lists, so it stays readable with CSS off.
 */
export function FileTree({ tree, className }: FileTreeProps) {
  return (
    <ul
      data-slot="file-tree"
      className={cn("w-full rounded-xl border bg-card p-3 font-mono", className)}
    >
      {tree.map((node) => (
        <Node key={node.name} node={node} depth={0} />
      ))}
    </ul>
  );
}
