export type NotificationChannel =
  | 'document'
  | 'agent'
  | 'system'
  | 'collab'
  | 'security';

export interface NotificationAction {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'ghost';
}
