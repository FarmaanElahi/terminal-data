import { useMutation } from "@tanstack/react-query";
import { preferencesApi } from "@/lib/api";
import type { WorkspaceState } from "@/types/layout";

export function useSaveLayoutMutation() {
  return useMutation({
    mutationFn: (layout: Partial<WorkspaceState>) =>
      preferencesApi.update({ layout }),
    retry: 3,
  });
}
