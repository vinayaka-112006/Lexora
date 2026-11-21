import ReactMarkdown from "react-markdown";

export default function MarkdownMessage({ children }) {
  return <ReactMarkdown>{children}</ReactMarkdown>;
}
