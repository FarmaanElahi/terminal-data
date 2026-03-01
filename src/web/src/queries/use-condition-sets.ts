import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { conditionsApi } from "@/lib/api";
import { QUERY_KEYS } from "./query-keys";
import type { ConditionSet } from "@/types/models";
import type { ConditionSetCreate, ConditionSetUpdate } from "@/types/api";

export function useConditionSetsQuery() {
  return useQuery<ConditionSet[]>({
    queryKey: QUERY_KEYS.conditionSets,
    queryFn: async () => {
      const { data } = await conditionsApi.all();
      return data;
    },
    staleTime: Infinity,
  });
}

export function useCreateConditionSetMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ConditionSetCreate) =>
      conditionsApi.create(data).then((r) => r.data),
    onSuccess: (newCs) => {
      queryClient.setQueryData<ConditionSet[]>(QUERY_KEYS.conditionSets, (old) =>
        old ? [...old, newCs] : [newCs],
      );
    },
  });
}

export function useUpdateConditionSetMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ConditionSetUpdate }) =>
      conditionsApi.update(id, data).then((r) => r.data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.conditionSets });
      const prev = queryClient.getQueryData<ConditionSet[]>(
        QUERY_KEYS.conditionSets,
      );
      queryClient.setQueryData<ConditionSet[]>(QUERY_KEYS.conditionSets, (old) =>
        old?.map((cs) => (cs.id === id ? ({ ...cs, ...data } as ConditionSet) : cs)) ?? [],
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData(QUERY_KEYS.conditionSets, ctx.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.conditionSets });
    },
  });
}

export function useDeleteConditionSetMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => conditionsApi.delete(id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.conditionSets });
      const prev = queryClient.getQueryData<ConditionSet[]>(
        QUERY_KEYS.conditionSets,
      );
      queryClient.setQueryData<ConditionSet[]>(QUERY_KEYS.conditionSets, (old) =>
        old?.filter((cs) => cs.id !== id) ?? [],
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData(QUERY_KEYS.conditionSets, ctx.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.conditionSets });
    },
  });
}
