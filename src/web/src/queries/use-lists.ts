import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listsApi } from "@/lib/api";
import { QUERY_KEYS } from "./query-keys";
import type { List } from "@/types/models";
import type { ListCreate, ListUpdate } from "@/types/api";

export function useListsQuery() {
  return useQuery<List[]>({
    queryKey: QUERY_KEYS.lists,
    queryFn: async () => {
      const { data } = await listsApi.all();
      return data;
    },
    staleTime: Infinity,
  });
}

export function useSetSymbolsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ listId, symbols }: { listId: string; symbols: string[] }) =>
      listsApi.setSymbols(listId, symbols),
    onMutate: async ({ listId, symbols }) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.lists });
      const prev = queryClient.getQueryData<List[]>(QUERY_KEYS.lists);
      queryClient.setQueryData<List[]>(QUERY_KEYS.lists, (old) =>
        old?.map((l) => (l.id === listId ? { ...l, symbols } : l)) ?? [],
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData(QUERY_KEYS.lists, ctx.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.lists });
    },
  });
}

export function useAddSymbolMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ listId, ticker }: { listId: string; ticker: string }) =>
      listsApi.appendSymbols(listId, [ticker]),
    onMutate: async ({ listId, ticker }) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.lists });
      const prev = queryClient.getQueryData<List[]>(QUERY_KEYS.lists);
      queryClient.setQueryData<List[]>(QUERY_KEYS.lists, (old) =>
        old?.map((l) =>
          l.id === listId
            ? { ...l, symbols: Array.from(new Set([...l.symbols, ticker])) }
            : l,
        ) ?? [],
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData(QUERY_KEYS.lists, ctx.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.lists });
    },
  });
}

export function useRemoveSymbolMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ listId, ticker }: { listId: string; ticker: string }) =>
      listsApi.removeSymbols(listId, [ticker]),
    onMutate: async ({ listId, ticker }) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.lists });
      const prev = queryClient.getQueryData<List[]>(QUERY_KEYS.lists);
      queryClient.setQueryData<List[]>(QUERY_KEYS.lists, (old) =>
        old?.map((l) =>
          l.id === listId
            ? { ...l, symbols: l.symbols.filter((s) => s !== ticker) }
            : l,
        ) ?? [],
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData(QUERY_KEYS.lists, ctx.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.lists });
    },
  });
}

export function useCreateListMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ListCreate) => listsApi.create(data).then((r) => r.data),
    onSuccess: (newList) => {
      queryClient.setQueryData<List[]>(QUERY_KEYS.lists, (old) =>
        old ? [...old, newList] : [newList],
      );
    },
  });
}

export function useUpdateListMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ListUpdate }) =>
      listsApi.update(id, data).then((r) => r.data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.lists });
      const prev = queryClient.getQueryData<List[]>(QUERY_KEYS.lists);
      queryClient.setQueryData<List[]>(QUERY_KEYS.lists, (old) =>
        old?.map((l) => (l.id === id ? { ...l, ...data } : l)) ?? [],
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData(QUERY_KEYS.lists, ctx.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.lists });
    },
  });
}

export function useDeleteListMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => listsApi.delete(id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.lists });
      const prev = queryClient.getQueryData<List[]>(QUERY_KEYS.lists);
      queryClient.setQueryData<List[]>(QUERY_KEYS.lists, (old) =>
        old?.filter((l) => l.id !== id) ?? [],
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData(QUERY_KEYS.lists, ctx.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.lists });
    },
  });
}

/**
 * Optimistic update for flag (color list) operations.
 * Adds ticker to targetListId and removes from all other color lists.
 */
export function useSetFlagMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      targetListId,
      ticker,
    }: {
      targetListId: string;
      ticker: string;
    }) => listsApi.appendSymbols(targetListId, [ticker]),
    onMutate: async ({ targetListId, ticker }) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.lists });
      const prev = queryClient.getQueryData<List[]>(QUERY_KEYS.lists);
      queryClient.setQueryData<List[]>(QUERY_KEYS.lists, (old) =>
        old?.map((l) => {
          if (l.type !== "color") return l;
          if (l.id === targetListId) {
            return {
              ...l,
              symbols: Array.from(new Set([...l.symbols, ticker])),
            };
          }
          return { ...l, symbols: l.symbols.filter((s) => s !== ticker) };
        }) ?? [],
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData(QUERY_KEYS.lists, ctx.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.lists });
    },
  });
}
