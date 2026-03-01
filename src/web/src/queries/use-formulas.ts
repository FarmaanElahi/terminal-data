import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formulaApi } from "@/lib/api";
import { QUERY_KEYS } from "./query-keys";
import type { Formula } from "@/types/models";
import type { FormulaCreate } from "@/types/api";

export function useFormulasQuery() {
  return useQuery<Formula[]>({
    queryKey: QUERY_KEYS.formulas,
    queryFn: async () => {
      const { data } = await formulaApi.all();
      return data;
    },
    staleTime: Infinity,
  });
}

export function useCreateFormulaMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: FormulaCreate) =>
      formulaApi.create(data).then((r) => r.data),
    onSuccess: (newFormula) => {
      queryClient.setQueryData<Formula[]>(QUERY_KEYS.formulas, (old) =>
        old ? [...old, newFormula] : [newFormula],
      );
    },
  });
}

export function useDeleteFormulaMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => formulaApi.delete(id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.formulas });
      const prev = queryClient.getQueryData<Formula[]>(QUERY_KEYS.formulas);
      queryClient.setQueryData<Formula[]>(QUERY_KEYS.formulas, (old) =>
        old?.filter((f) => f.id !== id) ?? [],
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData(QUERY_KEYS.formulas, ctx.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.formulas });
    },
  });
}
