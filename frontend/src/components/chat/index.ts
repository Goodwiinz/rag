export {
  ChatAnalytics,
  default as ChatAnalyticsComponent,
} from './ChatAnalytics';
export { ChatInput, default as ChatInputComponent } from './ChatInput';
export {
  ChatSettingsPanel,
  default as ChatSettingsPanelComponent,
} from './ChatSettings';
export { CitationLink, default as CitationLinkComponent } from './CitationLink';
export {
  CitationPanel,
  default as CitationPanelComponent,
} from './CitationPanel';
export {
  CitationPreview,
  default as CitationPreviewComponent,
} from './CitationPreview';
export {
  CitationRenderer,
  default as CitationRendererComponent,
} from './CitationRenderer';
export {
  ModelSelector,
  AVAILABLE_MODELS,
  default as ModelSelectorComponent,
} from './ModelSelector';

// Extracted components from chat page
export {
  ModelLoadingProgress,
  default as ModelLoadingProgressComponent,
} from './ModelLoadingProgress';
export { WelcomeState, default as WelcomeStateComponent } from './WelcomeState';
export { RAGToggle, default as RAGToggleComponent } from './RAGToggle';

// Shared chat primitives
export { TerminalChatBubble } from './shared/TerminalChatBubble';
export { TerminalChatComposer } from './shared/TerminalChatComposer';
export {
  mapChatMessageToViewModel,
  mapSearchResultToChatMessages,
} from './shared/messageViewModel';

// Re-export types
export type { ChatMetrics } from './ChatAnalytics';
export type { ChatSettings } from './ChatSettings';
export type { ModelLoadingProgressProps } from './ModelLoadingProgress';
export type { Model, ExtendedModel } from './ModelSelector';
export type { WelcomeStateProps } from './WelcomeState';
export type { RAGToggleProps } from './RAGToggle';
export type {
  TerminalChatBubbleProps,
  TerminalChatBubbleMessage,
} from './shared/TerminalChatBubble';
export type { TerminalChatComposerProps } from './shared/TerminalChatComposer';
export type { ChatMessageViewModel } from './shared/messageViewModel';
