import React from 'react';
function ReactMarkdown({ children, ...props }: any) {
  return <div data-testid="mock-react-markdown">{children}</div>;
}
export default ReactMarkdown;
