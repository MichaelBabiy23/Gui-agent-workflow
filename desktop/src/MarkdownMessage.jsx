import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function ExternalLink({ href, children }) {
  return (
    <a
      href={href}
      onClick={(event) => {
        event.preventDefault();
        window.workflow.openExternal(href).catch(() => {});
      }}
    >
      {children}
    </a>
  );
}

const components = { a: ExternalLink };

export default function MarkdownMessage({ text }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {text}
    </ReactMarkdown>
  );
}
