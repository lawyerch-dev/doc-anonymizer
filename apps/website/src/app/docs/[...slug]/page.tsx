import Link from "next/link";
import { notFound } from "next/navigation";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { DOCS, groupedDocs, readDoc, rewriteLinks, type DocEntry } from "@/lib/docs";

export const dynamicParams = false;

export function generateStaticParams() {
  return DOCS.map((d) => ({ slug: [d.slug] }));
}

function findDoc(slug: string[] | undefined): DocEntry | undefined {
  return DOCS.find((d) => d.slug === (slug ?? []).join("/"));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string[] }> }) {
  const doc = findDoc((await params).slug);
  return { title: doc ? `${doc.title} · doc-anonymizer` : "doc-anonymizer 文档" };
}

export default async function DocPage({ params }: { params: Promise<{ slug: string[] }> }) {
  const doc = findDoc((await params).slug);
  if (!doc) notFound();

  const markdown = rewriteLinks(readDoc(doc), doc);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 gap-10 px-6 py-10">
      <aside className="hidden w-56 shrink-0 lg:block">
        <Link href="/" className="text-sm font-medium">
          ← doc-anonymizer
        </Link>
        <nav className="mt-6 space-y-6 text-sm">
          {groupedDocs().map((g) => (
            <div key={g.group}>
              <div className="mb-2 text-xs text-muted-foreground">{g.group}</div>
              <ul className="space-y-1">
                {g.items.map((d) => (
                  <li key={d.slug}>
                    <Link
                      href={`/docs/${d.slug}`}
                      className={
                        d.slug === doc.slug
                          ? "font-medium text-foreground"
                          : "text-muted-foreground hover:text-foreground"
                      }
                    >
                      {d.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </aside>

      <article className="min-w-0 flex-1">
        <p className="mb-1 text-xs text-muted-foreground">
          {doc.group} · 源文件 <code>{doc.file}</code>
        </p>
        <h1 className="mb-6 text-3xl font-bold tracking-tight">{doc.title}</h1>
        <div className="prose prose-neutral dark:prose-invert max-w-none prose-pre:bg-muted prose-pre:text-foreground prose-code:before:content-none prose-code:after:content-none prose-table:text-sm">
          <Markdown remarkPlugins={[remarkGfm]}>{markdown}</Markdown>
        </div>
        <p className="mt-12 border-t pt-4 text-xs text-muted-foreground">
          内容直接来自仓库里的 <code>{doc.file}</code>，改文档就是改它（本站构建时读取）。
        </p>
      </article>
    </div>
  );
}
