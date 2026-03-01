import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { columnsApi } from "@/lib/api";
import { QUERY_KEYS } from "./query-keys";
import type { ColumnSet } from "@/types/models";
import type { ColumnSetCreate, ColumnSetUpdate } from "@/types/api";

export function useColumnSetsQuery() {
  return useQuery<ColumnSet[]>({
    queryKey: QUERY_KEYS.columnSets,
    queryFn: async () => {
      const { data } = await columnsApi.all();
      return data;
    },
    staleTime: Infinity,
  });
}

export function useCreateColumnSetMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ColumnSetCreate) =>
      columnsApi.create(data).then((r) => r.data),
    onSuccess: (newCs) => {
      queryClient.setQueryData<ColumnSet[]>(QUERY_KEYS.columnSets, (old) =>
        old ? [...old, newCs] : [newCs],
      );
    },
  });
}

export function useUpdateColumnSetMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ColumnSetUpdate }) =>
      columnsApi.update(id, data).then((r) => r.data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.columnSets });
      const prev = queryClient.getQueryData<ColumnSet[]>(QUERY_KEYS.columnSets);
      queryClient.setQueryData<ColumnSet[]>(QUERY_KEYS.columnSets, (old) =>
        old?.map((cs) => (cs.id === id ? { ...cs, ...data } : cs)) ?? [],
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData(QUERY_KEYS.columnSets, ctx.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.columnSets });
    },
  });
}

export function useDeleteColumnSetMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => columnsApi.delete(id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.columnSets });
      const prev = queryClient.getQueryData<ColumnSet[]>(QUERY_KEYS.columnSets);
      queryClient.setQueryData<ColumnSet[]>(QUERY_KEYS.columnSets, (old) =>
        old?.filter((cs) => cs.id !== id) ?? [],
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData(QUERY_KEYS.columnSets, ctx.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.columnSets });
    },
  });
}
