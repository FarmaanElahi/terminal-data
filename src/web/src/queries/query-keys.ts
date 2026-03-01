export const QUERY_KEYS = {
  lists: ["lists"] as const,
  columnSets: ["column-sets"] as const,
  conditionSets: ["condition-sets"] as const,
  formulas: ["formulas"] as const,
  preferences: ["preferences"] as const,
  communityFeed: (type: string, key: string) =>
    ["community-feed", type, key] as const,
};
