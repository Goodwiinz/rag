/**
 * Entity Permissions Hook
 *
 * Provides authorization checks for entity management operations
 * Based on user role (admin can create/edit/delete, all users can read)
 */

import { useAuth } from './useAuth';
import { EntityPermissions } from '@/types/entity';

/**
 * Hook to check entity operation permissions
 *
 * @returns EntityPermissions object with boolean flags for each operation
 */
export function useEntityPermissions(): EntityPermissions {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  return {
    canCreate: isAdmin,
    canEdit: isAdmin,
    canDelete: isAdmin,
    canBulkEdit: isAdmin,
    isAdmin,
  };
}
