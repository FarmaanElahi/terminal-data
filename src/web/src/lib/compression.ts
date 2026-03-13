/**
 * Data decompression utilities for API responses.
 * Converts column-oriented format back to array of objects.
 */

export interface CompressedData {
  columns: string[];
  values: any[][];
}

export interface SymbolData {
  ticker: string; // ID
  name: string;
  logo: string | null;
  exchange: string | null;
  market: string;
  type: string;
  typespecs: string[];
}

/**
 * Decompress column-oriented format back to array of objects.
 *
 * Converts:
 *   {
 *     "columns": ["a", "b"],
 *     "values": [[1, "x"], [2, "y"]]
 *   }
 *
 * To:
 *   [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
 *
 * @param compressed - Data in column-oriented format
 * @returns Array of objects
 */
export function decompressObjects<T = Record<string, any>>(
  compressed: CompressedData
): T[] {
  const { columns, values } = compressed;

  if (!columns || !values) {
    return [];
  }

  return values.map((row) =>
    Object.fromEntries(columns.map((col, idx) => [col, row[idx]]))
  ) as T[];
}

/**
 * Decompress symbols from boot API response.
 *
 * @param compressed - Compressed symbols data
 * @returns Array of symbol objects
 */
export function decompressSymbols(
  compressed: CompressedData
): SymbolData[] {
  return decompressObjects<SymbolData>(compressed);
}
