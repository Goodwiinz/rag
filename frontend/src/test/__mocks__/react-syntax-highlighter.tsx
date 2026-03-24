import React from 'react';
export const Prism = ({ children }: any) => <div data-testid="mock-prism">{children}</div>;
export const Light = ({ children }: any) => <div data-testid="mock-light">{children}</div>;
export const PrismLight = ({ children }: any) => <div data-testid="mock-prism-light">{children}</div>;
export default ({ children }: any) => <div data-testid="mock-syntax-highlighter">{children}</div>;
